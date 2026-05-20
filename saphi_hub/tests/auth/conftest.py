"""
tests/auth/conftest.py
======================
Fixtures compartidas para todos los tests de autenticación.

Sin pytest-asyncio extra — usamos asyncio.run() en cada test
para mantener cero dependencias de plugins externos en el sprint 1.
"""

from __future__ import annotations

import uuid

import pytest

from auth.application.use_cases.github_login import (
    TokenIssuerFn,
    make_github_login,
)
from auth.domain.entities import UserRole
from auth.domain.value_objects import AccessToken, GitHubRawRepo
from auth.infrastructure.github.fake_adapter import FakeGitHubOAuthAdapter
from auth.infrastructure.persistence.fake_unit_of_work import FakeUnitOfWork


# ---------------------------------------------------------------------------
# Token issuer stub — devuelve siempre el mismo token predecible
# ---------------------------------------------------------------------------

FAKE_TOKEN_VALUE = "fake.jwt.token"
FAKE_EXPIRES_IN  = 3600


def fake_issue_token(user_id: uuid.UUID, role: UserRole) -> AccessToken:
    return AccessToken(value=FAKE_TOKEN_VALUE, expires_in=FAKE_EXPIRES_IN)


# ---------------------------------------------------------------------------
# Repos de ejemplo reutilizables
# ---------------------------------------------------------------------------

PYTHON_REPOS: tuple[GitHubRawRepo, ...] = (
    GitHubRawRepo("api-rest",   "Python",     ["fastapi", "postgresql"], 10),
    GitHubRawRepo("cli-tool",   "Python",     ["click", "docker"],        4),
    GitHubRawRepo("ml-project", "Python",     ["pytorch", "jupyter"],     6),
)

MIXED_REPOS: tuple[GitHubRawRepo, ...] = (
    GitHubRawRepo("backend",   "Python",     ["fastapi"],        8),
    GitHubRawRepo("frontend",  "TypeScript", ["react", "nextjs"], 5),
    GitHubRawRepo("infra",     None,         ["docker", "k8s"],   2),
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def issue_token() -> TokenIssuerFn:
    return fake_issue_token
from typing import cast
from auth.domain.repositories import GithubProfileRepository, UserRepository
from auth.application.use_cases.github_login import GitHubLoginFn, make_github_login

def build_use_case(
    github: FakeGitHubOAuthAdapter,
    uow:    FakeUnitOfWork,
) -> GitHubLoginFn:
    return make_github_login(
        github=github,
        users=cast(UserRepository, uow.users),
        github_profiles=cast(GithubProfileRepository, uow.github_profiles),
        issue_token=fake_issue_token,
    )