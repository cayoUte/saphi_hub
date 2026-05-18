"""
auth/domain/errors.py
=====================
Errores de dominio para el flujo de autenticación con GitHub.

Todos son dataclasses inmutables para que puedan vivir dentro de Err[E]
y ser inspeccionados con pattern matching sin depender de mensajes de string.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Errores del flujo OAuth
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GitHubCodeExchangeError:
    """GitHub rechazó el código OAuth (expirado, ya usado, inválido)."""
    raw_response: str


@dataclass(frozen=True)
class GitHubApiError:
    """Llamada a la API de GitHub falló (rate-limit, red, 5xx)."""
    status_code: int
    detail: str


# ---------------------------------------------------------------------------
# Errores de valor de dominio
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvalidEmailError:
    """El email recibido de GitHub no tiene formato válido."""
    raw: str


@dataclass(frozen=True)
class InvalidSlugError:
    """No se pudo generar un slug único para el usuario."""
    attempted: str


# ---------------------------------------------------------------------------
# Errores de persistencia
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UserPersistenceError:
    """Fallo al crear o actualizar el usuario en la base de datos."""
    detail: str


@dataclass(frozen=True)
class GithubProfilePersistenceError:
    """Fallo al vincular el perfil de GitHub al usuario."""
    detail: str


# ---------------------------------------------------------------------------
# Errores de autenticación
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TokenExpiredError:
    """El JWT presentado ha expirado."""


@dataclass(frozen=True)
class TokenInvalidError:
    """El JWT no puede ser verificado (firma inválida, malformado)."""
    detail: str


@dataclass(frozen=True)
class UserInactiveError:
    """El usuario existe pero está desactivado."""
    user_id: str


# ---------------------------------------------------------------------------
# Unión discriminada pública
# ---------------------------------------------------------------------------

type AuthError = (
    GitHubCodeExchangeError
    | GitHubApiError
    | InvalidEmailError
    | InvalidSlugError
    | UserPersistenceError
    | GithubProfilePersistenceError
    | TokenExpiredError
    | TokenInvalidError
    | UserInactiveError
)

__all__: list[str] = [
    "GitHubCodeExchangeError",
    "GitHubApiError",
    "InvalidEmailError",
    "InvalidSlugError",
    "UserPersistenceError",
    "GithubProfilePersistenceError",
    "TokenExpiredError",
    "TokenInvalidError",
    "UserInactiveError",
    "AuthError",
]