"""
auth/infrastructure/github/fake_adapter.py
==========================================
Doble de test para GitHubOAuthPort.

Permite testear GitHubLoginUseCase sin hacer ninguna llamada HTTP.
Configurable por escenario: éxito, código inválido, API caída, sin email.

Uso:

    # Caso feliz — usuario nuevo con repos
    adapter = FakeGitHubOAuthAdapter.happy_path(
        github_id=12345,
        login="mruiz",
        name="María Ruiz",
        email="mruiz@epn.edu.ec",
        repos=[
            GitHubRawRepo("api-rest", "Python", ["fastapi", "postgresql"], 10),
            GitHubRawRepo("ml-project", "Python", ["pytorch", "jupyter"], 3),
        ],
    )

    # Código OAuth inválido
    adapter = FakeGitHubOAuthAdapter.invalid_code()

    # API de GitHub caída después del intercambio
    adapter = FakeGitHubOAuthAdapter.api_down()
"""

from __future__ import annotations

from dataclasses import dataclass, field

from auth.domain.entities import GitHubUserPayload
from auth.domain.errors import AuthError, GitHubApiError, GitHubCodeExchangeError
from auth.domain.value_objects import GitHubCode, GitHubRawRepo, GitHubToken
from shared.result import Err, Ok, Result


@dataclass
class FakeGitHubOAuthAdapter:
    """
    Doble configurable.

    Atributos:
        token_to_return:    Token que devuelve exchange_code (Ok).
        payload_to_return:  Payload que devuelve fetch_user (Ok).
        exchange_error:     Si está definido, exchange_code devuelve Err con este error.
        fetch_error:        Si está definido, fetch_user devuelve Err con este error.
        codes_seen:         Registro de códigos recibidos (útil para assertions).
        tokens_seen:        Registro de tokens usados en fetch_user.
    """

    token_to_return:   GitHubToken | None     = field(default=None)
    payload_to_return: GitHubUserPayload | None = field(default=None)
    exchange_error:    GitHubCodeExchangeError | GitHubApiError | None = field(default=None)
    fetch_error:       GitHubApiError | None  = field(default=None)

    codes_seen:  list[str] = field(default_factory=list)
    tokens_seen: list[str] = field(default_factory=list)

    # ── Implementación del protocolo ─────────────────────────────────────── #

    async def exchange_code(
        self, code: GitHubCode
    ) -> Result[GitHubToken, AuthError]:
        self.codes_seen.append(code.value)

        if self.exchange_error is not None:
            return Err(self.exchange_error)

        token = self.token_to_return or GitHubToken(value="fake-token-abc123")
        return Ok(token)

    async def fetch_user(
        self, token: GitHubToken
    ) -> Result[GitHubUserPayload, AuthError]:
        self.tokens_seen.append(token.value)

        if self.fetch_error is not None:
            return Err(self.fetch_error)

        payload = self.payload_to_return or _default_payload()
        return Ok(payload)

    # ── Factories por escenario ──────────────────────────────────────────── #

    @classmethod
    def happy_path(
        cls,
        github_id: int = 99001,
        login: str = "estudiante01",
        name: str = "Estudiante Prueba",
        email: str | None = "estudiante@epn.edu.ec",
        repos: tuple[GitHubRawRepo, ...] | None = None,
    ) -> FakeGitHubOAuthAdapter:
        """Flujo completo sin errores."""
        return cls(
            token_to_return=GitHubToken(value="ghp_fake_token"),
            payload_to_return=GitHubUserPayload(
                github_id=github_id,
                login=login,
                name=name,
                email=email,
                repos=repos or _default_repos(),
            ),
        )

    @classmethod
    def invalid_code(cls) -> FakeGitHubOAuthAdapter:
        """GitHub rechaza el código (expirado o ya usado)."""
        return cls(
            exchange_error=GitHubCodeExchangeError(
                raw_response="bad_verification_code"
            )
        )

    @classmethod
    def api_down(cls) -> FakeGitHubOAuthAdapter:
        """Exchange OK, pero la API de GitHub cae al pedir el perfil."""
        return cls(
            token_to_return=GitHubToken(value="ghp_fake_token"),
            fetch_error=GitHubApiError(
                status_code=503,
                detail="GitHub API unavailable",
            ),
        )

    @classmethod
    def no_email(cls) -> FakeGitHubOAuthAdapter:
        """Usuario que ocultó su email en GitHub."""
        return cls(
            token_to_return=GitHubToken(value="ghp_fake_token"),
            payload_to_return=GitHubUserPayload(
                github_id=99002,
                login="anonimo_dev",
                name="Anónimo Dev",
                email=None,
                repos=_default_repos(),
            ),
        )

    @classmethod
    def no_repos(cls) -> FakeGitHubOAuthAdapter:
        """Cuenta nueva sin repositorios — skills vacías."""
        return cls(
            token_to_return=GitHubToken(value="ghp_fake_token"),
            payload_to_return=GitHubUserPayload(
                github_id=99003,
                login="nuevo_usuario",
                name="Nuevo Usuario",
                email="nuevo@espol.edu.ec",
                repos=(),
            ),
        )


# ---------------------------------------------------------------------------
# Datos por defecto
# ---------------------------------------------------------------------------

def _default_repos() -> tuple[GitHubRawRepo, ...]:
    return (
        GitHubRawRepo(
            name="backend-api",
            language="Python",
            topics=["fastapi", "postgresql", "docker"],
            stargazers_count=12,
        ),
        GitHubRawRepo(
            name="ml-experiments",
            language="Python",
            topics=["pytorch", "jupyter", "scikit-learn"],
            stargazers_count=5,
        ),
        GitHubRawRepo(
            name="frontend-app",
            language="TypeScript",
            topics=["react", "nextjs"],
            stargazers_count=8,
        ),
    )


def _default_payload() -> GitHubUserPayload:
    return GitHubUserPayload(
        github_id=99000,
        login="test_user",
        name="Test User",
        email="test@epn.edu.ec",
        repos=_default_repos(),
    )


__all__: list[str] = ["FakeGitHubOAuthAdapter"]