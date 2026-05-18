"""
app/core/config.py
==================
Configuración centralizada con pydantic-settings.

Todas las variables de entorno se definen aquí.
Nada más importa os.environ directamente.
"""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base de datos
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # GitHub OAuth
    GITHUB_CLIENT_ID:     str
    GITHUB_CLIENT_SECRET: str

    # Encriptación de access_token de GitHub
    TOKEN_ENCRYPTION_KEY: str

    # CORS — lista separada por comas en el .env
    # Ejemplo: CORS_ORIGINS=http://localhost:3000,https://acadex.dev
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()   # type: ignore[call-arg]  # pydantic-settings lee el .env


__all__: list[str] = ["Settings", "settings"]