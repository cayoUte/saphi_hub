"""
auth/application/use_cases/github_login.py
==========================================
Caso de uso: US-01 — Registrarse / iniciar sesión con GitHub.

Estilo funcional:
  - `make_github_login` es una función de orden superior que recibe las
    dependencias y devuelve un Callable (la función `execute`).
  - No hay clase. No hay self. Las dependencias son closures.
  - Cada paso intermedio es una función local pura o casi-pura
    (las que llaman a repos tienen efecto pero devuelven Result).

  `TokenIssuerPort` se modela como alias de Callable — tiene un único
  comportamiento y no necesita una interfaz con nombre de clase.

  `GitHubOAuthPort` sigue siendo Protocol porque tiene dos métodos
  semánticamente distintos que es útil nombrar explícitamente.

Flujo (Railway Oriented):

  GitHubCode
    │
    ├─ exchange_code()         Ok(GitHubToken)   | Err(GitHubCodeExchangeError)
    ├─ fetch_user()            Ok(Payload)        | Err(GitHubApiError)
    ├─ resolve_email()         Ok(Email)          | Err(InvalidEmailError)
    ├─ find_or_create_user()   Ok((User, bool))   | Err(*)
    ├─ build_identity()        GithubIdentity     (puro, no falla)
    ├─ save_identity()         Ok(identity)       | Err(GithubProfilePersistenceError)
    ├─ extract + save skills   best-effort        (no interrumpe el flujo)
    └─ issue_token()           AccessToken        (no falla)
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, cast

from auth.domain.entities import (
    GithubIdentity,
    Skill,
    User,
    UserRole,
    apply_skills,
    create_user,
    link_github,
)
from auth.domain.errors import AuthError, InvalidEmailError
from auth.domain.repositories import GithubProfileRepository, UserRepository
from auth.domain.services import extract_skills_from_repos, generate_unique_slug
from auth.domain.value_objects import (
    AccessToken,
    Email,
    GitHubCode,
    GitHubToken,
    GitHubUserPayload,
    UserSlug,
)
from shared.option import Nothing, Some
from shared.result import Err, Ok, Result


# ---------------------------------------------------------------------------
# Puertos
# ---------------------------------------------------------------------------

class GitHubOAuthPort(Protocol):
    async def exchange_code(
        self, code: GitHubCode
    ) -> Result[GitHubToken, AuthError]: ...

    async def fetch_user(
        self, token: GitHubToken
    ) -> Result[GitHubUserPayload, AuthError]: ...


# TokenIssuer no necesita Protocol — es un Callable con firma conocida.
type TokenIssuerFn = Callable[[uuid.UUID, UserRole], AccessToken]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GitHubLoginOutput:
    user:         User
    access_token: AccessToken
    is_new_user:  bool


# ---------------------------------------------------------------------------
# Tipo del caso de uso
# ---------------------------------------------------------------------------

type GitHubLoginFn = Callable[[GitHubCode], Awaitable[Result[GitHubLoginOutput, AuthError]]]


# ---------------------------------------------------------------------------
# Constructor del caso de uso
# ---------------------------------------------------------------------------

def make_github_login(
    github:          GitHubOAuthPort,
    users:           UserRepository,
    github_profiles: GithubProfileRepository,
    issue_token:     TokenIssuerFn,
) -> GitHubLoginFn:
    """
    Recibe las dependencias y devuelve la función `execute` lista para usar.

    Las dependencias quedan capturadas en el closure — no hay estado mutable,
    solo referencias a los puertos inyectados.
    """

    async def execute(code: GitHubCode) -> Result[GitHubLoginOutput, AuthError]:

        # 1 ── Intercambiar código OAuth por token de GitHub
        match await github.exchange_code(code):
            case Err() as err:  return err
            case Ok(value=token): pass

        # 2 ── Obtener perfil y repos del usuario
        match await github.fetch_user(token):
            case Err() as err:    return err
            case Ok(value=payload): pass

        # 3 ── Resolver email (GitHub puede no exponerlo)
        match _resolve_email(payload):
            case Err() as err:
                return cast(Result[GitHubLoginOutput, AuthError], err)
            case Ok(value=email): pass

        # 4 ── Encontrar o crear usuario
        match _find_or_create(email, payload, users, github_profiles):
            case Err() as err:           return err
            case Ok(value=(user, is_new)): pass

        # 5 ── Construir identidad de GitHub y persistirla
        identity = _build_identity(user.id, token, payload)
        match github_profiles.save(identity):
            case Err() as err:
                return cast(Result[GitHubLoginOutput, AuthError], err)
            case Ok(): pass

        # 6 ── Vincular identidad al valor User (produce User nuevo)
        user = link_github(user, identity)

        # 7 ── Extraer y persistir skills (best-effort — no interrumpe el login)
        user = _sync_skills(user, payload, users)

        # 8 ── Emitir JWT
        token_out = issue_token(user.id, user.role)

        return Ok(GitHubLoginOutput(user=user, access_token=token_out, is_new_user=is_new))

    return execute


# ---------------------------------------------------------------------------
# Funciones locales puras / casi-puras
# ---------------------------------------------------------------------------

def _resolve_email(payload: GitHubUserPayload) -> Result[Email, InvalidEmailError]:
    """
    GitHub omite el email cuando el usuario lo oculta en su perfil.
    En ese caso usamos el noreply address que GitHub asigna internamente.
    """
    raw = payload.email or f"{payload.login}@users.noreply.github.com"
    return Email.create(raw)


def _find_or_create(
    email:           Email,
    payload:         GitHubUserPayload,
    users:           UserRepository,
    github_profiles: GithubProfileRepository,
) -> Result[tuple[User, bool], AuthError]:
    """
    Estrategia de lookup (en orden de prioridad):
      1. github_id  → el más estable; cubre cambio de email en GitHub.
      2. email      → usuario que ya existía antes de conectar GitHub.
      3. nuevo      → primera vez en la plataforma.

    Devuelve (User, is_new).
    """
    # 1. Buscar por github_id
    match github_profiles.find_by_github_id(payload.github_id):
        case Some(value=identity):
            match users.find_by_id(identity.user_id):
                case Some(value=existing_user):
                    return Ok((existing_user, False))
                case Nothing():
                    pass   # perfil huérfano — tratar como nuevo

    # 2. Buscar por email
    match users.find_by_email(email):
        case Some(value=existing_user):
            return Ok((existing_user, False))
        case Nothing():
            pass

    # 3. Crear usuario nuevo
    return _create_new_user(email, payload, users)


def _create_new_user(
    email:   Email,
    payload: GitHubUserPayload,
    users:   UserRepository,
) -> Result[tuple[User, bool], AuthError]:
    display_name = payload.name or payload.login
    prefix       = display_name.split()[0].lower() if display_name else payload.login
    existing     = users.existing_slugs_starting_with(prefix)

    match generate_unique_slug(display_name, existing):
        case Err() as err:
            return cast(Result[tuple[User, bool], AuthError], err)
        case Ok(value=slug):
            pass

    new_user = create_user(email=email, display_name=display_name, slug=slug)

    match users.save(new_user):
        case Err() as err:
            return cast(Result[tuple[User, bool], AuthError], err)
        case Ok(value=saved_user): return Ok((saved_user, True))


def _build_identity(
    user_id: uuid.UUID,
    token:   GitHubToken,
    payload: GitHubUserPayload,
) -> GithubIdentity:
    """Construye la identidad de GitHub — función pura, no falla."""
    return GithubIdentity(
        id=uuid.uuid4(),
        user_id=user_id,
        github_id=payload.github_id,
        github_login=payload.login,
        access_token=token,
        raw_repos=payload.repos,
        synced_at=datetime.now(timezone.utc),
    )


def _sync_skills(
    user:    User,
    payload: GitHubUserPayload,
    users:   UserRepository,
) -> User:
    """
    Extrae skills de los repos y las persiste.
    Best-effort: si falla la persistencia, devuelve el User con skills
    en memoria pero sin interrumpir el flujo de login.
    """
    skills: tuple[Skill, ...] = tuple(extract_skills_from_repos(payload.repos))
    users.save_skills(user.id, skills)   # ignoramos el Result — best-effort
    return apply_skills(user, skills)


__all__: list[str] = [
    "GitHubOAuthPort",
    "TokenIssuerFn",
    "GitHubLoginOutput",
    "GitHubLoginFn",
    "make_github_login",
]