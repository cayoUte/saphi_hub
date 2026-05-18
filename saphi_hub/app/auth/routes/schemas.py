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

from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class SkillOut(BaseModel):
    name:     str
    category: str
    weight:   int = Field(ge=1, le=100)

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id:           uuid.UUID
    role:         str
    email:        str
    display_name: str
    slug:         str
    is_active:    bool
    created_at:   datetime

    model_config = {"from_attributes": True}


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
    token_type:   str         = "bearer"
    expires_in:   int
    is_new_user:  bool
    user:         UserOut
    skills:       list[SkillOut]


class RedirectURLResponse(BaseModel):
    """
    URL a la que el frontend debe redirigir al usuario para iniciar OAuth.
    """
    url: str


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


__all__: list[str] = [
    "SkillOut",
    "UserOut",
    "GitHubLoginResponse",
    "RedirectURLResponse",
    "APIErrorResponse",
    "CurrentUserResponse",
]