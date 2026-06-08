"""
auth/domain/entities.py
=======================
Entidades de dominio — datos inmutables + funciones puras.

Reglas aplicadas:
  - Todos los dataclasses son frozen=True. Ningún campo se muta jamás.
  - El comportamiento que antes era método se convierte en función de módulo
    que recibe la entidad y devuelve una entidad nueva via dataclasses.replace().
  - Ninguna función tiene efectos secundarios observables.
  - `create_user` reemplaza al classmethod User.create().

Esto garantiza que las entidades son valores, no objetos con identidad.
Dos User con los mismos campos son indistinguibles — igual que un int.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum

from auth.domain.value_objects import Email, GitHubRawRepo, GitHubToken, GitHubUserPayload, UserSlug


# ---------------------------------------------------------------------------
# UserRole
# ---------------------------------------------------------------------------

class UserRole(StrEnum):
    student     = "student"
    institution = "institution"
    admin       = "admin"
    mentor      = "mentor"


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Skill:
    name:     str
    category: str   # "language" | "topic" | "framework"
    weight:   int   # 1–100


# ---------------------------------------------------------------------------
# GithubIdentity
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GithubIdentity:
    """
    Perfil de GitHub vinculado a un usuario.
    github_id es el identificador estable — github_login puede cambiar.
    """
    id:           uuid.UUID
    user_id:      uuid.UUID
    github_id:    int
    github_login: str
    access_token: GitHubToken
    raw_repos:    tuple[GitHubRawRepo, ...]
    synced_at:    datetime


# ---------------------------------------------------------------------------
# User  — dato inmutable
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class User:
    """
    Valor inmutable que representa un usuario del sistema.

    No tiene métodos de comportamiento — las transformaciones son funciones
    puras en este módulo que devuelven un User nuevo via dataclasses.replace().

    github_identity y skills usan tuple para mantener la hashabilidad total.
    """
    id:              uuid.UUID
    role:            UserRole
    email:           Email
    display_name:    str
    slug:            UserSlug
    is_active:       bool
    created_at:      datetime
    updated_at:      datetime
    github_identity: GithubIdentity | None  = field(default=None)
    skills:          tuple[Skill, ...]      = field(default_factory=tuple)

# ---------------------------------------------------------------------------
# Funciones puras de transformación
# ---------------------------------------------------------------------------

def create_user(
    email:        Email,
    display_name: str,
    slug:         UserSlug,
    role:         UserRole = UserRole.student,
) -> User:
    """Construye un User nuevo con id generado y timestamps UTC."""
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        role=role,
        email=email,
        display_name=display_name,
        slug=slug,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def link_github(user: User, identity: GithubIdentity) -> User:
    """Devuelve un nuevo User con el perfil de GitHub vinculado."""
    return replace(
        user,
        github_identity=identity,
        updated_at=datetime.now(timezone.utc),
    )


def apply_skills(user: User, skills: tuple[Skill, ...]) -> User:
    """Devuelve un nuevo User con las skills reemplazadas."""
    return replace(
        user,
        skills=skills,
        updated_at=datetime.now(timezone.utc),
    )


def deactivate(user: User) -> User:
    """Devuelve un nuevo User desactivado."""
    return replace(user, is_active=False, updated_at=datetime.now(timezone.utc))


__all__: list[str] = [
    "UserRole",
    "Skill",
    "GithubIdentity",
    "User",
    "GitHubUserPayload",
    "create_user",
    "link_github",
    "apply_skills",
    "deactivate",
]