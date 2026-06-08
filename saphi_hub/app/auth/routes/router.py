"""
auth/routes/router.py 
=====================
Endpoints HTTP del módulo de autenticación.

  GET  /auth/github/redirect   → URL de autorización de GitHub
  GET  /auth/github/callback   → intercambia code, devuelve JWT + perfil
  GET  /auth/me                → perfil del usuario autenticado

Cambios respecto a la versión anterior:
  - El caso de uso se obtiene como Callable (GitHubLoginFn), no como clase.
  - El router no conoce GitHubLoginUseCase — solo conoce GitHubLoginFn.
  - User es frozen; se accede a sus campos directamente sin mutar nada.
  - _raise_http_error usa exhaustive match sobre AuthError.
"""

from __future__ import annotations

import urllib.parse
import uuid
from typing import Annotated, NoReturn, TypedDict, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import HttpUrl

from auth.application.use_cases.github_login import GitHubLoginFn, GitHubLoginOutput
from auth.domain.entities import User
from auth.domain.errors import (
    GithubProfilePersistenceError,
    GitHubApiError,
    GitHubCodeExchangeError,
    InvalidEmailError,
    InvalidSlugError,
    TokenExpiredError,
    TokenInvalidError,
    UserInactiveError,
    UserPersistenceError,
)
from auth.domain.value_objects import GitHubCode
from auth.infrastructure.container import AuthContainer
from auth.routes.schemas import (
    CurrentUserResponse,
    GitHubLoginResponse,
    RedirectURLResponse,
    UserOut,
)
from shared.option import Nothing, Some
from shared.result import Err, Ok

router      = APIRouter()
_oauth2     = OAuth2PasswordBearer(tokenUrl="/auth/github/callback", auto_error=False)
_GITHUB_URL = "https://github.com/login/oauth/authorize"
_SCOPES     = "read:user user:email"


class JWTPayload(TypedDict):
    sub:  str
    role: str
    exp:  int
    iat:  int


# ---------------------------------------------------------------------------
# Dependencias
# ---------------------------------------------------------------------------

def _container(request: Request) -> AuthContainer:
    return request.app.state.auth


# ---------------------------------------------------------------------------
# GET /auth/github/redirect
# ---------------------------------------------------------------------------

@router.get("/github/redirect", response_model=RedirectURLResponse)
def github_redirect(
    container: Annotated[AuthContainer, Depends(_container)],
) -> RedirectURLResponse:
    params = urllib.parse.urlencode({
        "client_id": container.github_client_id,
        "scope":     _SCOPES,
    })
    return RedirectURLResponse(url=cast(HttpUrl, f"{_GITHUB_URL}?{params}"))


# ---------------------------------------------------------------------------
# GET /auth/github/callback
# ---------------------------------------------------------------------------

@router.get("/github/callback", response_model=GitHubLoginResponse)
async def github_callback(
    code:      Annotated[str, Query()],
    container: Annotated[AuthContainer, Depends(_container)],
) -> GitHubLoginResponse:
    uow = container.new_uow()

    with uow:
        execute = container.github_login(uow)
        result  = await execute(GitHubCode(value=code))
        match result:
            case Ok(value=output):
                uow.commit()
                return _to_login_response(output)
            case Err(error=error):
                _raise_http_error(error)


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
)
def get_me(
    token:     Annotated[str | None, Depends(_oauth2)],
    container: Annotated[AuthContainer, Depends(_container)],
) -> CurrentUserResponse:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    match container.token_issuer.decode(token):
        case Err(error=TokenExpiredError()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        case Err(error=TokenInvalidError(detail=d)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token inválido: {d}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        case Ok(value=payload):
            jwt_payload = cast(JWTPayload, payload)

            uow = container.new_uow()
            with uow:
                user_opt = uow.users.find_by_id(uuid.UUID(jwt_payload["sub"]))

            match user_opt:
                case Nothing():
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
                case Some(value=domain_user):
                    if not domain_user.is_active:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Cuenta desactivada",
                        )
                    return CurrentUserResponse.from_user(domain_user)

    raise RuntimeError("JWT decode match should be exhaustive")

def _to_login_response(output: GitHubLoginOutput) -> GitHubLoginResponse:
    return GitHubLoginResponse.from_output(output)


def _to_user_out(user: User) -> UserOut:
    return UserOut.from_domain(user)


def _raise_http_error(error: object) -> NoReturn:
    """Convierte AuthError de dominio en HTTPException. Exhaustivo por diseño."""
    match error:
        case GitHubCodeExchangeError():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Código OAuth inválido o expirado. Inicia el flujo de nuevo.",
            )
        case GitHubApiError(status_code=sc):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"GitHub API no disponible (HTTP {sc}). Intenta más tarde.",
            )
        case InvalidEmailError(raw=r):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Email inválido recibido de GitHub: '{r}'",
            )
        case InvalidSlugError(attempted=a):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No se pudo generar un slug para '{a}'",
            )
        case UserPersistenceError(detail=d) | GithubProfilePersistenceError(detail=d):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno al guardar datos: {d}",
            )
        case UserInactiveError(user_id=uid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"La cuenta {uid} está desactivada.",
            )
        case _:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error inesperado en autenticación.",
            )


__all__: list[str] = ["router", "JWTPayload"]
