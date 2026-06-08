"""
auth/infrastructure/github/adapter.py
======================================
Adaptador HTTP que implementa GitHubOAuthPort usando httpx.AsyncClient.

Responsabilidades:
  1. exchange_code  → POST a GitHub para obtener el access_token.
  2. fetch_user     → GET /user, /user/emails, /user/repos y ensambla GitHubUserPayload.

Principios:
  - El cliente httpx se inyecta; nunca se crea aquí.
    Quién gestiona el ciclo de vida: el lifespan de FastAPI.
  - Todos los errores de red o de API se convierten en Err(AuthError).
    El caso de uso nunca maneja excepciones crudas.
  - Los repos se obtienen solo en la primera página (100 repos, ordenados
    por actividad reciente). Suficiente para extraer skills en el sprint 1.

Scopes OAuth requeridos en GitHub App:
    read:user   → /user y /user/emails
    repo        → /user/repos (repos privados)
    (sin write:* — solo lectura)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from auth.domain.entities import GitHubUserPayload
from auth.domain.errors import GitHubApiError, GitHubCodeExchangeError
from auth.domain.value_objects import GitHubCode, GitHubRawRepo, GitHubToken
from shared.result import Err, Ok, Result

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modelos Pydantic privados para respuestas de GitHub API
# ---------------------------------------------------------------------------

class _GitHubTokenResponse(BaseModel):
    """Respuesta de POST /login/oauth/access_token"""
    access_token: str | None = None
    error: str | None = None
    error_description: str | None = None


class _GitHubProfileResponse(BaseModel):
    """Respuesta de GET /user"""
    id: int
    login: str
    name: str | None = None
    email: str | None = None


class _GitHubEmailEntry(BaseModel):
    """Entrada de GET /user/emails"""
    email: str
    primary: bool
    verified: bool


class _GitHubRepoEntry(BaseModel):
    """Entrada de GET /user/repos"""
    name: str
    language: str | None = None
    topics: list[str] = Field(default_factory=list)
    stargazers_count: int = 0
    fork: bool = False

# ---------------------------------------------------------------------------
# Constantes de la API de GitHub
# ---------------------------------------------------------------------------

_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
_API_BASE        = "https://api.github.com"

_GITHUB_HEADERS = {
    "Accept":               "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


# ---------------------------------------------------------------------------
# Adaptador
# ---------------------------------------------------------------------------

class GitHubOAuthAdapter:
    """
    Implementación concreta de GitHubOAuthPort.

    Args:
        client_id:     Client ID de la GitHub App/OAuth App.
        client_secret: Client Secret correspondiente.
        http:          httpx.AsyncClient compartido (creado en el lifespan).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        http: httpx.AsyncClient,
    ) -> None:
        self._client_id     = client_id
        self._client_secret = client_secret
        self._http          = http

    # ── exchange_code ────────────────────────────────────────────────────── #

    async def exchange_code(
        self, code: GitHubCode
    ) -> Result[GitHubToken, GitHubCodeExchangeError | GitHubApiError]:
        """
        POST https://github.com/login/oauth/access_token

        GitHub devuelve JSON con `access_token` si todo va bien,
        o `error` + `error_description` si el código es inválido/expirado.

        El código es de un solo uso — GitHub lo invalida tras el primer intento.
        """
        try:
            response = await self._http.post(
                _OAUTH_TOKEN_URL,
                json={
                    "client_id":     self._client_id,
                    "client_secret": self._client_secret,
                    "code":          code.value,
                },
                headers={"Accept": "application/json"},
                timeout=10.0,
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            return Err(GitHubApiError(
                status_code=exc.response.status_code,
                detail=f"GitHub OAuth endpoint respondió {exc.response.status_code}",
            ))
        except httpx.RequestError as exc:
            logger.warning("Error de red al contactar GitHub OAuth: %s", exc)
            return Err(GitHubApiError(status_code=0, detail=f"Error de red: {exc}"))

        # Validar respuesta con Pydantic
        try:
            data = _GitHubTokenResponse.model_validate(response.json())
        except ValidationError as exc:
            logger.error("GitHub devolvió JSON inválido: %s", exc)
            return Err(GitHubApiError(
                status_code=response.status_code,
                detail="Respuesta inválida de GitHub"
            ))

        # GitHub devuelve 200 incluso cuando hay error; el error viene en el cuerpo.
        if data.error:
            description = data.error_description or data.error
            logger.info("GitHub rechazó el código OAuth: %s", description)
            return Err(GitHubCodeExchangeError(raw_response=description))

        if not data.access_token:
            return Err(GitHubCodeExchangeError(
                raw_response="GitHub no devolvió access_token en la respuesta"
            ))

        return Ok(GitHubToken.create(data.access_token))

    # ── fetch_user ───────────────────────────────────────────────────────── #

    async def fetch_user(
        self, token: GitHubToken
    ) -> Result[GitHubUserPayload, GitHubApiError]:
        """
        Obtiene perfil, emails y repos del usuario autenticado.

        Tres llamadas en secuencia (no en paralelo — el sprint 1 no lo necesita):
          1. GET /user          → id, login, name, email público
          2. GET /user/emails   → email primario verificado (si /user no lo expone)
          3. GET /user/repos    → hasta 100 repos ordenados por push reciente
        """
        auth_headers = {**_GITHUB_HEADERS, "Authorization": f"Bearer {token.value}"}

        # 1. Perfil principal - hacer request inline con validación Pydantic
        try:
            resp = await self._http.get(f"{_API_BASE}/user", headers=auth_headers, timeout=10.0)
            resp.raise_for_status()
            profile = _GitHubProfileResponse.model_validate(resp.json())
        except httpx.HTTPStatusError as exc:
            logger.warning("GitHub API /user devolvió %s", exc.response.status_code)
            return Err(GitHubApiError(
                status_code=exc.response.status_code,
                detail=_extract_github_message(exc.response),
            ))
        except httpx.RequestError as exc:
            logger.warning("Error de red en GET /user: %s", exc)
            return Err(GitHubApiError(status_code=0, detail=f"Error de red: {exc}"))
        except ValidationError as exc:
            logger.error("GitHub /user devolvió JSON inválido: %s", exc)
            return Err(GitHubApiError(status_code=200, detail="Respuesta inválida de GitHub"))

        # 2. Email: GitHub puede devolver null si el usuario lo ocultó.
        email = profile.email
        if not email:
            email = await self._fetch_primary_email(auth_headers)

        # 3. Repos
        repos = await self._fetch_repos(auth_headers)

        return Ok(GitHubUserPayload(
            github_id=profile.id,
            login=profile.login,
            name=profile.name,
            email=email,
            repos=tuple(repos),
        ))

    # ── helpers privados ─────────────────────────────────────────────────── #

    async def _fetch_primary_email(self, headers: dict[str, str]) -> str | None:
        """
        GET /user/emails — devuelve el email primario verificado, o None.

        Si el scope `read:user` no fue otorgado, GitHub devuelve 404.
        En ese caso fallamos silenciosamente — _resolve_email del caso de uso
        construirá un email derivado del login.
        """
        try:
            response = await self._http.get(
                f"{_API_BASE}/user/emails", headers=headers, timeout=10.0
            )
            if response.status_code != 200:
                return None
            
            # Validar cada entrada con Pydantic
            entries = [_GitHubEmailEntry.model_validate(e) for e in response.json()]
            
            # Preferimos email primario + verificado; si no, cualquier primario.
            for entry in entries:
                if entry.primary and entry.verified:
                    return entry.email
            for entry in entries:
                if entry.primary:
                    return entry.email
            return None

        except (httpx.RequestError, ValidationError):
            return None

    async def _fetch_repos(self, headers: dict[str, str]) -> list[GitHubRawRepo]:
        """
        GET /user/repos?type=owner&sort=pushed&per_page=100

        - type=owner: solo repos propios, no forks (los forks sesgan las skills).
        - sort=pushed: repos más activos primero.
        - per_page=100: máximo permitido por GitHub.

        Si la llamada falla (scope insuficiente, rate-limit) devuelve lista vacía.
        El caso de uso maneja esto como best-effort.
        """
        try:
            response = await self._http.get(
                f"{_API_BASE}/user/repos",
                headers=headers,
                params={"type": "owner", "sort": "pushed", "per_page": "100"},
                timeout=15.0,   # repos puede ser lento con muchos objetos
            )
            if response.status_code != 200:
                logger.warning("No se pudieron obtener repos: HTTP %s", response.status_code)
                return []

            # Validar cada repo con Pydantic
            entries = [_GitHubRepoEntry.model_validate(r) for r in response.json()]
            
            return [
                GitHubRawRepo(
                    name=entry.name,
                    language=entry.language,
                    topics=entry.topics,
                    stargazers_count=entry.stargazers_count,
                )
                for entry in entries
                if not entry.fork   # excluir forks explícitamente
            ]

        except (httpx.RequestError, ValidationError) as exc:
            logger.warning("Error obteniendo repos: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Helpers de módulo
# ---------------------------------------------------------------------------

def _extract_github_message(response: httpx.Response) -> str:
    """Extrae el campo `message` del JSON de error de GitHub, si existe."""
    try:
        return response.json().get("message", response.text)
    except Exception:
        return response.text


__all__: list[str] = ["GitHubOAuthAdapter"]