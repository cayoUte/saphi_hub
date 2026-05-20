"""
app/main.py
===========
Punto de entrada de la aplicación FastAPI.

Responsabilidades:
  - Definir el lifespan (startup / shutdown).
  - Inicializar el contenedor de infraestructura una sola vez.
  - Registrar los routers.
  - Montar middleware global.

Lo que NO hace:
  - Lógica de negocio.
  - Acceso directo a la DB.
  - Imports de SQLAlchemy.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from auth.infrastructure.container import AuthContainer
from auth.routes.router import router as auth_router


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Construye la infraestructura en startup y la libera en shutdown.

    app.state.auth  →  AuthContainer (singleton durante la vida de la app)
    """
    container = AuthContainer.from_settings(settings)
    app.state.auth = container

    yield   # la app sirve requests aquí

    await container.close()


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Acadex API",
    version="0.1.0",
    description="Plataforma de colaboración académica — Sprint 1",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Manejador global de excepciones no controladas
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Captura cualquier excepción que no fue convertida en HTTPException.
    Loguea el detalle internamente; al cliente solo llega un mensaje genérico.
    """
    import logging
    logging.getLogger("uvicorn.error").exception(
        "Excepción no controlada en %s %s", request.method, request.url
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": "internal_error", "message": "Error interno del servidor"},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router, prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["ops"], summary="Estado del servicio")
def health() -> dict:
    return {"status": "ok", "version": app.version}