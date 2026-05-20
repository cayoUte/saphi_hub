"""
auth/infrastructure/persistence/fake_unit_of_work.py
====================================================
UoW en memoria para tests unitarios del caso de uso.

No toca Postgres. No necesita fixtures de DB. Corre en microsegundos.

Uso en tests:

    def test_new_user_gets_skills():
        uow = FakeUnitOfWork()
        github = FakeGitHubOAuthAdapter(user=sample_payload)
        use_case = GitHubLoginUseCase(github, uow.users, uow.github_profiles, FakeTokenIssuer())

        with uow:
            result = asyncio.run(use_case.execute(GitHubCode("code-xyz")))
            uow.commit()

        assert result
        user = result.unwrap().user
        assert len(user.skills) > 0
        assert uow.committed
"""

from __future__ import annotations

import uuid
from types import TracebackType
from typing import Self

from auth.domain.entities import GithubIdentity, Skill, User
from auth.domain.value_objects import Email
from auth.domain.errors import GithubProfilePersistenceError, UserPersistenceError
from shared.option import Nothing, Option, Some
from shared.result import Err, Ok, Result


# ---------------------------------------------------------------------------
# Repositorios en memoria
# ---------------------------------------------------------------------------

class FakeUserRepository:
    def __init__(self) -> None:
        self._store:       dict[uuid.UUID, User]                  = {}
        self._skill_store: dict[uuid.UUID, tuple[Skill, ...]]     = {}

    def find_by_id(self, user_id: uuid.UUID) -> Option[User]:
        user = self._store.get(user_id)
        return Some(user) if user else Nothing()

    def find_by_email(self, email: Email) -> Option[User]:
        for user in self._store.values():
            if user.email.value == email.value:
                return Some(user)
        return Nothing()

    def find_by_github_id(self, github_id: int) -> Option[User]:
        # Delega: necesita cruzar con github_profiles
        # En tests reales se puede inyectar el repo de perfiles o simplificar.
        return Nothing()

    def existing_slugs_starting_with(self, prefix: str) -> frozenset[str]:
        return frozenset(
            u.slug.value
            for u in self._store.values()
            if u.slug.value.startswith(prefix)
        )

    def save(self, user: User) -> Result[User, UserPersistenceError]:
        self._store[user.id] = user
        return Ok(user)

    def save_skills(
        self, user_id: uuid.UUID, skills: tuple[Skill, ...]
    ) -> Result[None, UserPersistenceError]:
        # User es frozen — las skills se persisten por separado.
        # En tests verificamos skills en el User devuelto por el caso de uso,
        # no en el store (que contiene el User pre-apply_skills).
        self._skill_store[user_id] = skills
        return Ok(None)


class FakeGithubProfileRepository:
    def __init__(self) -> None:
        self._store: dict[int, GithubIdentity] = {}   # github_id → identity

    def find_by_github_id(self, github_id: int) -> Option[GithubIdentity]:
        identity = self._store.get(github_id)
        return Some(identity) if identity else Nothing()

    def find_by_user_id(self, user_id: uuid.UUID) -> Option[GithubIdentity]:
        for identity in self._store.values():
            if identity.user_id == user_id:
                return Some(identity)
        return Nothing()

    def save(
        self, identity: GithubIdentity
    ) -> Result[GithubIdentity, GithubProfilePersistenceError]:
        self._store[identity.github_id] = identity
        return Ok(identity)


# ---------------------------------------------------------------------------
# FakeUnitOfWork
# ---------------------------------------------------------------------------

class FakeUnitOfWork:
    """
    UoW en memoria que satisface el protocolo AbstractUnitOfWork.
    committed=True indica que el caso de uso llamó commit() sin errores.
    """

    committed: bool = False
    rolled_back: bool = False

    def __init__(self) -> None:
        self.users           = FakeUserRepository()
        self.github_profiles = FakeGithubProfileRepository()

    def __enter__(self) -> Self:
        self.committed   = False
        self.rolled_back = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val:  BaseException | None,
        exc_tb:   TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.rollback()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


__all__: list[str] = [
    "FakeUnitOfWork",
    "FakeUserRepository",
    "FakeGithubProfileRepository",
]