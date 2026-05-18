"""
auth/infrastructure/persistence/repositories/user_repository.py
===============================================================
Implementación SQLAlchemy del puerto UserRepository.

Recibe una Session de SQLAlchemy — la UoW es quien la provee y
controla su ciclo de vida (commit/rollback/close).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from auth.domain.entities import Skill, User
from auth.domain.errors import UserPersistenceError
from auth.domain.value_objects import Email
from auth.infrastructure.persistence.mappers import (
    orm_to_skill,
    orm_to_user,
    skill_to_skill_orm,
    skill_to_user_skill_orm,
    user_to_orm,
)
from auth.infrastructure.persistence.orm_models import (
    SkillORM,
    UserORM,
    UserSkillORM,
)
from shared.option import Nothing, Option, Some
from shared.result import Err, Ok, Result


class SQLAlchemyUserRepository:
    """
    Implementación concreta de UserRepository sobre SQLAlchemy.

    Invariante: nunca llama a session.commit() — eso es responsabilidad
    exclusiva de la UnitOfWork.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Lecturas ─────────────────────────────────────────────────────────── #

    def find_by_id(self, user_id: uuid.UUID) -> Option[User]:
        row = self._session.get(UserORM, user_id)
        if row is None:
            return Nothing()
        return Some(orm_to_user(row))

    def find_by_email(self, email: Email) -> Option[User]:
        stmt = select(UserORM).where(UserORM.email == email.value)
        row = self._session.scalars(stmt).first()
        if row is None:
            return Nothing()
        return Some(orm_to_user(row))

    def find_by_github_id(self, github_id: int) -> Option[User]:
        """
        Busca el usuario a través de su github_profile vinculado.
        Hace un JOIN implícito via la relación ORM.
        """
        from auth.infrastructure.persistence.orm_models import GithubProfileORM

        stmt = (
            select(UserORM)
            .join(GithubProfileORM, GithubProfileORM.user_id == UserORM.id)
            .where(GithubProfileORM.github_id == github_id)
        )
        row = self._session.scalars(stmt).first()
        if row is None:
            return Nothing()
        return Some(orm_to_user(row))

    def existing_slugs_starting_with(self, prefix: str) -> frozenset[str]:
        stmt = select(UserORM.slug).where(UserORM.slug.like(f"{prefix}%"))
        return frozenset(self._session.scalars(stmt).all())

    # ── Escrituras ───────────────────────────────────────────────────────── #

    def save(self, user: User) -> Result[User, UserPersistenceError]:
        try:
            existing = self._session.get(UserORM, user.id)
            row = user_to_orm(user, existing=existing)
            if existing is None:
                self._session.add(row)
            self._session.flush()   # obtiene el id sin commitear
            return Ok(orm_to_user(row))

        except IntegrityError as exc:
            self._session.rollback()
            return Err(UserPersistenceError(
                detail=f"Violación de unicidad al guardar usuario: {exc.orig}"
            ))
        except SQLAlchemyError as exc:
            self._session.rollback()
            return Err(UserPersistenceError(detail=str(exc)))

    def save_skills(
        self, user_id: uuid.UUID, skills: tuple[Skill, ...]
    ) -> Result[None, UserPersistenceError]:
        """
        Reemplaza todas las skills del usuario con upsert por nombre.

        Estrategia:
          1. Eliminar las UserSkillORM existentes del usuario.
          2. Para cada Skill: obtener o crear el SkillORM por nombre.
          3. Crear el UserSkillORM vinculando user ↔ skill.
          4. flush() — sin commit.
        """
        try:
            # 1. Borrar relaciones anteriores (no las skills globales)
            self._session.query(UserSkillORM).filter(
                UserSkillORM.user_id == user_id
            ).delete(synchronize_session="fetch")

            for skill in skills:
                # 2. Upsert del catálogo de skills
                skill_row = self._session.scalars(
                    select(SkillORM).where(SkillORM.name == skill.name)
                ).first()

                if skill_row is None:
                    skill_row = skill_to_skill_orm(skill)
                    self._session.add(skill_row)
                    self._session.flush()   # necesitamos skill_row.id

                # 3. Crear vínculo user ↔ skill
                user_skill = skill_to_user_skill_orm(user_id, skill_row.id, skill)
                self._session.add(user_skill)

            self._session.flush()
            return Ok(None)

        except SQLAlchemyError as exc:
            self._session.rollback()
            return Err(UserPersistenceError(detail=str(exc)))


__all__: list[str] = ["SQLAlchemyUserRepository"]