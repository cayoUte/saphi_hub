"""
auth/domain/value_objects.py
============================
Value objects del dominio de autenticación.

Reglas:
  - Inmutables (frozen dataclass).
  - Construcción validada vía classmethod `create` que devuelve Result.
  - Sin dependencias de infraestructura.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from shared.result import Err, Ok, Result
from auth.domain.errors import InvalidEmailError, InvalidSlugError


# ---------------------------------------------------------------------------
# GitHubCode
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GitHubCode:
    """
    Código temporal emitido por GitHub al finalizar el paso de autorización.
    Es un string opaco; solo GitHub sabe qué contiene.
    """
    value: str

    @classmethod
    def create(cls, raw: str) -> Result[GitHubCode, InvalidSlugError]:
        if not raw or not raw.strip():
            return Err(InvalidSlugError(attempted=raw))
        return Ok(cls(value=raw.strip()))


# ---------------------------------------------------------------------------
# GitHubToken
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GitHubToken:
    """Access token obtenido tras intercambiar el GitHubCode."""
    value: str

    # Sin validación extra: GitHub es quien define el formato.
    @classmethod
    def create(cls, raw: str) -> GitHubToken:
        return cls(value=raw)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Email:
    value: str

    @classmethod
    def create(cls, raw: str) -> Result[Email, InvalidEmailError]:
        normalized = raw.strip().lower()
        if not _EMAIL_RE.match(normalized):
            return Err(InvalidEmailError(raw=raw))
        return Ok(cls(value=normalized))


# ---------------------------------------------------------------------------
# UserSlug
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class UserSlug:
    value: str

    @classmethod
    def from_display_name(cls, display_name: str, suffix: int = 0) -> Result[UserSlug, InvalidSlugError]:
        """
        Genera un slug URL-safe a partir del display_name.

        Ejemplo:
            "María José Ruiz" → "maria-jose-ruiz"
            "María José Ruiz" (colisión) → "maria-jose-ruiz-2"
        """
        # Normalizar unicode → ASCII
        normalized = unicodedata.normalize("NFD", display_name)
        ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_str.lower()).strip("-")

        if suffix > 0:
            slug = f"{slug}-{suffix}"

        if not slug or not _SLUG_RE.match(slug):
            return Err(InvalidSlugError(attempted=display_name))

        return Ok(cls(value=slug))


# ---------------------------------------------------------------------------
# AccessToken  (JWT emitido por nuestro sistema)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AccessToken:
    """JWT firmado listo para entregar al cliente."""
    value: str
    expires_in: int   # segundos


# ---------------------------------------------------------------------------
# GitHubRawRepo  (DTO del payload de la API de GitHub)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GitHubRawRepo:
    """
    Representación mínima de un repositorio de GitHub.
    Se extrae del campo `raw_repos` de la API.
    """
    name: str
    language: str | None
    topics: list[str]
    stargazers_count: int

@dataclass(frozen=True)
class GitHubUserPayload:
    """
    Datos crudos de la API de GitHub.
    La infra lo construye; el dominio lo consume como input de funciones puras.
    """
    github_id: int
    login:     str
    name:      str | None
    email:     str | None
    repos:     tuple[GitHubRawRepo, ...]

__all__: list[str] = [
    "GitHubCode",
    "GitHubToken",
    "Email",
    "UserSlug",
    "AccessToken",
    "GitHubRawRepo",
    "GitHubUserPayload",
]