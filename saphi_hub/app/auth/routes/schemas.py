"""
auth/routes/schemas.py
======================
Schemas Pydantic para los endpoints de autenticación.

Separados de las entidades de dominio a propósito:
  - El dominio no conoce Pydantic ni HTTP.
  - Los schemas pueden cambiar (versioning de API) sin tocar el dominio.
  - La serialización ocurre aquí, no en las entidades.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, cast

from pydantic import BaseModel, EmailStr, Field, HttpUrl

from auth.application.use_cases.github_login import GitHubLoginOutput
from auth.domain.entities import Skill, User, UserRole


# ---------------------------------------------------------------------------
# Alias de tipo — contrato de la API
# ---------------------------------------------------------------------------

SkillCategory = Literal["language", "topic", "framework", "other"]
TokenType     = Literal["bearer"]


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class SkillOut(BaseModel):
    name:     str
    category: SkillCategory
    weight:   int = Field(ge=1, le=100)

    model_config = {"from_attributes": True}

    @classmethod
    def from_domain(cls, skill: Skill) -> SkillOut:
        return cls(
            name=skill.name,
            category=cast(SkillCategory, skill.category),
            weight=skill.weight,
        )


class UserOut(BaseModel):
    id:           uuid.UUID
    role:         UserRole
    email:        EmailStr
    display_name: str
    slug:         str
    is_active:    bool
    created_at:   datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_domain(cls, user: User) -> UserOut:
        return cls(
            id=user.id,
            role=user.role,
            email=user.email.value,
            display_name=user.display_name,
            slug=user.slug.value,
            is_active=user.is_active,
            created_at=user.created_at,
        )


class GitHubLoginResponse(BaseModel):
    """
    Respuesta del callback OAuth.

    access_token:  JWT para incluir en Authorization: Bearer <token>.
    token_type:    Siempre "bearer" (RFC 6750).
    expires_in:    Segundos hasta que el token expira.
    is_new_user:   True si se creó la cuenta en este request.
    user:          Perfil del usuario autenticado.
    skills:        Skills extraídas de sus repos de GitHub.
    """
    access_token: str
    token_type:   TokenType = "bearer"
    expires_in:   int
    is_new_user:  bool
    user:         UserOut
    skills:       list[SkillOut]

    @classmethod
    def from_output(cls, output: GitHubLoginOutput) -> GitHubLoginResponse:
        return cls(
            access_token=output.access_token.value,
            expires_in=output.access_token.expires_in,
            is_new_user=output.is_new_user,
            user=UserOut.from_domain(output.user),
            skills=[SkillOut.from_domain(s) for s in output.user.skills],
        )


class RedirectURLResponse(BaseModel):
    """
    URL a la que el frontend debe redirigir al usuario para iniciar OAuth.
    """
    url: HttpUrl


# ---------------------------------------------------------------------------
# Errores de API  (cuerpo estándar para todos los 4xx/5xx de este módulo)
# ---------------------------------------------------------------------------

class APIErrorResponse(BaseModel):
    code:    str
    message: str


# ---------------------------------------------------------------------------
# Request  (solo para el endpoint /me — no necesita body, pero documentamos)
# ---------------------------------------------------------------------------

class CurrentUserResponse(BaseModel):
    user:   UserOut
    skills: list[SkillOut]

    @classmethod
    def from_user(cls, user: User) -> CurrentUserResponse:
        return cls(
            user=UserOut.from_domain(user),
            skills=[SkillOut.from_domain(s) for s in user.skills],
        )


__all__: list[str] = [
    "SkillCategory",
    "TokenType",
    "SkillOut",
    "UserOut",
    "GitHubLoginResponse",
    "RedirectURLResponse",
    "APIErrorResponse",
    "CurrentUserResponse",
]
