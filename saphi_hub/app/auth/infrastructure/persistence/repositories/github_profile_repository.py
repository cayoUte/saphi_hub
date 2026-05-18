"""
auth/infrastructure/persistence/repositories/github_profile_repository.py
=========================================================================
Implementación SQLAlchemy del puerto GithubProfileRepository.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from auth.domain.entities import GithubIdentity
from auth.domain.errors import GithubProfilePersistenceError
from auth.infrastructure.persistence.mappers import (
    github_identity_to_orm,
    orm_to_github_identity,
)
from auth.infrastructure.persistence.orm_models import GithubProfileORM
from shared.option import Nothing, Option, Some
from shared.result import Err, Ok, Result


class SQLAlchemyGithubProfileRepository:
    """
    Implementación concreta de GithubProfileRepository.
    Nunca llama a session.commit() — eso es responsabilidad de la UoW.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Lecturas ─────────────────────────────────────────────────────────── #

    def find_by_github_id(self, github_id: int) -> Option[GithubIdentity]:
        stmt = select(GithubProfileORM).where(GithubProfileORM.github_id == github_id)
        row = self._session.scalars(stmt).first()
        if row is None:
            return Nothing()
        return Some(orm_to_github_identity(row))

    def find_by_user_id(self, user_id: uuid.UUID) -> Option[GithubIdentity]:
        stmt = select(GithubProfileORM).where(GithubProfileORM.user_id == user_id)
        row = self._session.scalars(stmt).first()
        if row is None:
            return Nothing()
        return Some(orm_to_github_identity(row))

    # ── Escrituras ───────────────────────────────────────────────────────── #

    def save(
        self, identity: GithubIdentity
    ) -> Result[GithubIdentity, GithubProfilePersistenceError]:
        """
        Upsert: si ya existe un perfil para este user_id, lo actualiza.
        Cubre el caso de re-autenticación (token rotado, login cambiado).
        """
        try:
            stmt = select(GithubProfileORM).where(
                GithubProfileORM.user_id == identity.user_id
            )
            existing = self._session.scalars(stmt).first()

            row = github_identity_to_orm(identity, existing=existing)
            if existing is None:
                self._session.add(row)

            self._session.flush()
            return Ok(orm_to_github_identity(row))

        except IntegrityError as exc:
            self._session.rollback()
            return Err(GithubProfilePersistenceError(
                detail=f"Conflicto de unicidad en github_profiles: {exc.orig}"
            ))
        except SQLAlchemyError as exc:
            self._session.rollback()
            return Err(GithubProfilePersistenceError(detail=str(exc)))


__all__: list[str] = ["SQLAlchemyGithubProfileRepository"]