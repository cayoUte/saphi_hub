"""
auth/infrastructure/container.py
=================================
Contenedor de dependencias del módulo auth.

Construye los singletons de infra y expone una factory que devuelve
el caso de uso como Callable — no como clase.

    use_case: GitHubLoginFn = container.github_login(uow)

La UoW se pasa al momento de construir el caso de uso por request,
porque su ciclo de vida es por-request, no por-app.
"""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session, sessionmaker

from auth.application.use_cases.github_login import (
    GitHubLoginFn,
    make_github_login,
)

from auth.infrastructure.persistence.unit_of_work import (
    SQLAlchemyUnitOfWork,
    build_session_factory,
    make_uow,
)
from auth.infrastructure.security.token_issuer import JWTTokenIssuer
from app.core.config import Settings
from saphi_hub.app.auth.infrastructure.github.adapter import GitHubOAuthAdapter


class AuthContainer:
    """
    Singleton de infraestructura para el módulo auth.
    Creado una vez en el lifespan de FastAPI; compartido entre requests.
    """

    def __init__(
        self,
        http_client:     httpx.AsyncClient,
        session_factory: sessionmaker[Session],
        github_adapter:  GitHubOAuthAdapter,
        token_issuer:    JWTTokenIssuer,
    ) -> None:
        self._http_client     = http_client
        self._session_factory = session_factory
        self._github          = github_adapter
        self.token_issuer     = token_issuer

    @classmethod
    def from_settings(cls, settings: Settings) -> AuthContainer:
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, read=15.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        return cls(
            http_client=http_client,
            session_factory=build_session_factory(settings.DATABASE_URL),
            github_adapter=GitHubOAuthAdapter(
                client_id=settings.GITHUB_CLIENT_ID,
                client_secret=settings.GITHUB_CLIENT_SECRET,
                http=http_client,
            ),
            token_issuer=JWTTokenIssuer(
                secret_key=settings.SECRET_KEY,
                expires_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            ),
        )

    # ── Por-request ─────────────────────────────────────────────────────── #

    def new_uow(self) -> SQLAlchemyUnitOfWork:
        """UoW nueva por cada request."""
        return make_uow(self._session_factory)

    def github_login(self, uow: SQLAlchemyUnitOfWork) -> GitHubLoginFn:
        """
        Construye el caso de uso como Callable, inyectando la UoW del request.

        Uso en el router:
            uow = container.new_uow()
            execute = container.github_login(uow)
            with uow:
                result = await execute(code)
        """
        return make_github_login(
            github=self._github,
            users=uow.users,                   # type: ignore[arg-type]
            github_profiles=uow.github_profiles, # type: ignore[arg-type]
            issue_token=self.token_issuer.issue,  # Callable directo — sin wrapper
        )

    @property
    def github_client_id(self) -> str:
        """Expone el client_id sin exponer el adaptador completo."""
        return self._github._client_id

    # ── Cierre ───────────────────────────────────────────────────────────── #

    async def close(self) -> None:
        await self._http_client.aclose()


__all__: list[str] = ["AuthContainer"]