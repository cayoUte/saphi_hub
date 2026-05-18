"""
auth/infrastructure/persistence/unit_of_work.py
===============================================
Patrón Unit of Work para el módulo de autenticación.

Responsabilidades:
  - Crear y cerrar la sesión de SQLAlchemy.
  - Proveer los repositorios que comparten esa sesión.
  - Hacer commit atómico de todos los cambios del caso de uso.
  - Hacer rollback automático si el bloque `with` lanza una excepción.

Contrato de uso en el caso de uso:

    with uow:
        user_result = uow.users.save(user)
        profile_result = uow.github_profiles.save(identity)
        if user_result and profile_result:
            uow.commit()
        # Si no se llama commit(), el __exit__ hace rollback.

La UoW NO decide si commitear — esa lógica pertenece al caso de uso.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self, runtime_checkable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from auth.domain.repositories import GithubProfileRepository, UserRepository
from auth.infrastructure.persistence.repositories.github_profile_repository import (
    SQLAlchemyGithubProfileRepository,
)
from auth.infrastructure.persistence.repositories.user_repository import (
    SQLAlchemyUserRepository,
)


# ---------------------------------------------------------------------------
# Puerto: AbstractUnitOfWork
# ---------------------------------------------------------------------------

@runtime_checkable
class AbstractUnitOfWork(Protocol):
    """
    Interfaz que el caso de uso conoce.
    Permite testear con una UoW en memoria sin tocar Postgres.
    """

    users:           UserRepository
    github_profiles: GithubProfileRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val:  BaseException | None,
        exc_tb:   TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


# ---------------------------------------------------------------------------
# Implementación SQLAlchemy
# ---------------------------------------------------------------------------

class SQLAlchemyUnitOfWork:
    """
    Implementación concreta de AbstractUnitOfWork usando SQLAlchemy síncrono.

    Recibe una `session_factory` (resultado de `sessionmaker(...)`) para que
    el engine y la configuración del pool se definan una sola vez en la capa
    de composición (main.py / dependencias FastAPI).

    Por qué síncrono en el sprint 1:
      Los repos son sync; la única I/O async es la llamada HTTP a GitHub,
      que ocurre ANTES de entrar a la UoW. Migrar a AsyncSession requiere
      async with, await session.execute(), etc. — lo haremos cuando el
      profiling lo justifique.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    # ── Repositorios (accesibles solo dentro del bloque with) ─────────────── #

    @property
    def users(self) -> SQLAlchemyUserRepository:
        self._assert_open()
        return SQLAlchemyUserRepository(self._session)   # type: ignore[arg-type]

    @property
    def github_profiles(self) -> SQLAlchemyGithubProfileRepository:
        self._assert_open()
        return SQLAlchemyGithubProfileRepository(self._session)   # type: ignore[arg-type]

    # ── Ciclo de vida ────────────────────────────────────────────────────── #

    def __enter__(self) -> SQLAlchemyUnitOfWork:
        self._session = self._session_factory()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val:  BaseException | None,
        exc_tb:   TracebackType | None,
    ) -> None:
        """
        Si el bloque termina con excepción → rollback automático.
        Si el caso de uso ya llamó commit() → close() sin efecto extra.
        """
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            if self._session:
                self._session.close()
                self._session = None

    def commit(self) -> None:
        self._assert_open()
        self._session.commit()   # type: ignore[union-attr]

    def rollback(self) -> None:
        if self._session:
            self._session.rollback()

    # ── Guard ────────────────────────────────────────────────────────────── #

    def _assert_open(self) -> None:
        if self._session is None:
            raise RuntimeError(
                "SQLAlchemyUnitOfWork: intento de acceder a repositorios "
                "fuera del bloque 'with'. Usa 'with uow: ...'."
            )


# ---------------------------------------------------------------------------
# Factory helper  (para inyección en FastAPI)
# ---------------------------------------------------------------------------

def build_session_factory(database_url: str) -> sessionmaker[Session]:
    """
    Crea el engine y la session_factory una sola vez al arrancar la app.

    Parámetros del pool ajustados para un monolito de sprint 1:
      pool_size=5       conexiones persistentes.
      max_overflow=10   conexiones extras bajo pico.
      pool_pre_ping     valida la conexión antes de usarla (detecta drops de red).
    """
    engine = create_engine(
        database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def make_uow(session_factory: sessionmaker[Session]) -> SQLAlchemyUnitOfWork:
    """Devuelve una nueva UoW lista para usar en un bloque with."""
    return SQLAlchemyUnitOfWork(session_factory)


__all__: list[str] = [
    "AbstractUnitOfWork",
    "SQLAlchemyUnitOfWork",
    "build_session_factory",
    "make_uow",
]