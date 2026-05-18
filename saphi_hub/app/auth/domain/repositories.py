"""
auth/domain/repositories.py
============================
Puertos (interfaces) que el dominio requiere de la infraestructura.

El dominio define QUÉ necesita; la infraestructura define CÓMO lo provee.
Esto permite testear el dominio con implementaciones en memoria.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from auth.domain.entities import GithubIdentity, Skill, User
from auth.domain.value_objects import Email, UserSlug
from shared.option import Option
from shared.result import Result
from auth.domain.errors import (
    GithubProfilePersistenceError,
    UserPersistenceError,
)


class UserRepository(Protocol):
    """Acceso a usuarios en el almacén de persistencia."""

    def find_by_id(self, user_id: uuid.UUID) -> Option[User]:
        """Devuelve Some(User) si existe, Nothing si no."""
        ...

    def find_by_email(self, email: Email) -> Option[User]:
        ...

    def find_by_github_id(self, github_id: int) -> Option[User]:
        ...

    def existing_slugs_starting_with(self, prefix: str) -> frozenset[str]:
        """
        Devuelve todos los slugs que empiezan con `prefix`.
        Usado por generate_unique_slug para evitar colisiones.
        """
        ...

    def save(self, user: User) -> Result[User, UserPersistenceError]:
        """Inserta o actualiza el usuario."""
        ...

    def save_skills(
        self, user_id: uuid.UUID, skills: tuple[Skill, ...]
    ) -> Result[None, UserPersistenceError]:
        """Reemplaza todas las skills del usuario."""
        ...


class GithubProfileRepository(Protocol):
    """Acceso a perfiles de GitHub vinculados."""

    def find_by_github_id(self, github_id: int) -> Option[GithubIdentity]:
        ...

    def find_by_user_id(self, user_id: uuid.UUID) -> Option[GithubIdentity]:
        ...

    def save(
        self, identity: GithubIdentity
    ) -> Result[GithubIdentity, GithubProfilePersistenceError]:
        ...


__all__: list[str] = [
    "UserRepository",
    "GithubProfileRepository",
]