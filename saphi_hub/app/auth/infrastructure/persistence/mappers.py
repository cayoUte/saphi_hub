"""
auth/infrastructure/persistence/mappers.py
==========================================
Conversión bidireccional entre modelos ORM y entidades de dominio.

  orm_to_*  →  ORM row   → entidad de dominio   (lectura desde DB)
  *_to_orm  →  entidad   → ORM row               (escritura hacia DB)

Reglas:
  - Nunca importar SQLAlchemy en el dominio.
  - Los mappers son las únicas funciones que conocen ambos mundos.
  - Retornan objetos nuevos; nunca mutan los inputs.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, cast

from auth.domain.entities import GithubIdentity, Skill, User, UserRole
from auth.domain.value_objects import (
    Email,
    GitHubRawRepo,
    GitHubToken,
    UserSlug,
)
from auth.infrastructure.persistence.orm_models import (
    GithubProfileORM,
    SkillORM,
    UserORM,
    UserSkillORM,
)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

def orm_to_user(row: UserORM) -> User:
    return User(
        id=row.id,
        role=UserRole(row.role),
        email=Email(value=row.email),
        display_name=row.display_name,
        slug=UserSlug(value=row.slug),
        is_active=row.is_active,
        created_at=_ensure_tz(row.created_at),
        updated_at=_ensure_tz(row.updated_at),
        github_identity=(
            orm_to_github_identity(row.github_profile)
            if row.github_profile else None
        ),
        skills=tuple(
            orm_to_skill(us)
            for us in (row.user_skills or [])
        ),
    )


def user_to_orm(user: User, existing: UserORM | None = None) -> UserORM:
    """
    Si se pasa `existing`, actualiza sus campos en lugar de crear uno nuevo.
    Esto preserva la identidad del objeto dentro de la sesión SQLAlchemy
    y evita conflictos de session.merge vs session.add.
    """
    target = existing or UserORM()
    target.id           = user.id
    target.role         = user.role.value
    target.email        = user.email.value
    target.display_name = user.display_name
    target.slug         = user.slug.value
    target.is_active    = user.is_active
    target.created_at   = user.created_at
    target.updated_at   = user.updated_at
    return target


# ---------------------------------------------------------------------------
# GithubIdentity
# ---------------------------------------------------------------------------

def orm_to_github_identity(row: GithubProfileORM) -> GithubIdentity:
    raw_repos_data = cast(list[dict[str, Any]] | None, row.raw_repos)  # type: ignore[arg-type]
    return GithubIdentity(
        id=row.id,
        user_id=row.user_id,
        github_id=row.github_id,
        github_login=row.github_login,
        access_token=GitHubToken(value=row.access_token),
        raw_repos=tuple(_parse_raw_repos(raw_repos_data)),
        synced_at=_ensure_tz(row.synced_at),
    )


def github_identity_to_orm(
    identity: GithubIdentity,
    existing: GithubProfileORM | None = None,
) -> GithubProfileORM:
    target = existing or GithubProfileORM()
    target.id           = identity.id
    target.user_id      = identity.user_id
    target.github_id    = identity.github_id
    target.github_login = identity.github_login
    target.access_token = identity.access_token.value   # EncryptedString lo cifra al persistir
    target.raw_repos    = cast(Any, _serialize_raw_repos(identity.raw_repos))
    target.synced_at    = identity.synced_at
    return target


# ---------------------------------------------------------------------------
# Skill / UserSkill
# ---------------------------------------------------------------------------

def orm_to_skill(row: UserSkillORM) -> Skill:
    return Skill(
        name=row.skill.name,
        category=row.skill.category or "other",
        weight=row.weight,
    )


def skill_to_skill_orm(skill: Skill, existing: SkillORM | None = None) -> SkillORM:
    target = existing or SkillORM(id=uuid.uuid4())
    target.name     = skill.name
    target.category = skill.category
    return target


def skill_to_user_skill_orm(
    user_id: uuid.UUID,
    skill_id: uuid.UUID,
    skill: Skill,
) -> UserSkillORM:
    row = UserSkillORM()
    row.user_id  = user_id
    row.skill_id = skill_id
    row.source   = "github"
    row.weight   = skill.weight
    return row


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _ensure_tz(dt: datetime) -> datetime:
    """Garantiza que el datetime tenga tzinfo=UTC (Postgres puede devolverlo sin tz)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_raw_repos(raw: list[dict[str, Any]] | None) -> list[GitHubRawRepo]:
    if not raw:
        return []
    result: list[GitHubRawRepo] = []
    for item in raw:
        result.append(GitHubRawRepo(
            name=item.get("name", "") or "",
            language=item.get("language"),
            topics=list(item.get("topics") or []),
            stargazers_count=int(item.get("stargazers_count") or 0),
        ))
    return result


def _serialize_raw_repos(repos: Sequence[GitHubRawRepo]) -> list[dict[str, Any]]:
    return [
        {
            "name": r.name,
            "language": r.language,
            "topics": r.topics,
            "stargazers_count": r.stargazers_count,
        }
        for r in repos
    ]


__all__: list[str] = [
    "orm_to_user",
    "user_to_orm",
    "orm_to_github_identity",
    "github_identity_to_orm",
    "orm_to_skill",
    "skill_to_skill_orm",
    "skill_to_user_skill_orm",
]