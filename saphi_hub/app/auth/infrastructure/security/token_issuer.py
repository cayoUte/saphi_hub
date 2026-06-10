"""
auth/infrastructure/security/token_issuer.py
============================================
Implementación concreta de TokenIssuerPort.

Emite JWTs firmados con HMAC-SHA256 (HS256).

Estructura del payload:
    {
        "sub":  "<user_id>",       # subject estándar RFC 7519
        "role": "<user_role>",     # claim privado para autorización
        "iat":  <issued_at>,       # emitido en (UTC epoch)
        "exp":  <expiry>,          # expira en (UTC epoch)
    }

Por qué HS256 y no RS256 en sprint 1:
  HS256 es simétrico — una sola clave para firmar y verificar.
  Suficiente cuando el firmante y el verificador son el mismo servicio.
  RS256 (asimétrico) tiene sentido cuando múltiples servicios verifican
  tokens sin compartir el secret — típico en microservicios maduros.
  La migración es un cambio de algoritmo + clave, sin tocar el dominio.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict, cast

from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from auth.domain.entities import UserRole
from auth.domain.errors import TokenExpiredError, TokenInvalidError
from auth.domain.value_objects import AccessToken
from shared.result import Err, Ok, Result


_ALGORITHM = "HS256"


def _validate_payload(raw: dict[str, Any]) -> _JWTPayload:
    """
    Valida que el payload decodificado tenga la estructura esperada.
    
    Reemplaza el cast ciego con validación explícita de tipos y campos.
    Si la validación falla, lanza JWTError que será capturada por decode().
    
    Args:
        raw: Diccionario retornado por jwt.decode()
        
    Returns:
        Payload tipado como _JWTPayload después de validación exitosa
        
    Raises:
        JWTError: Si faltan campos requeridos o los tipos son incorrectos
    """
    # Verificar que todos los campos requeridos existen
    if not all(k in raw for k in ("sub", "role", "iat", "exp")):
        raise JWTError("missing required claims")
    
    # Verificar tipos de los campos string
    if not isinstance(raw["sub"], str) or not isinstance(raw["role"], str):
        raise JWTError("invalid claim types")
    
    # Cast seguro: ya validamos estructura y tipos arriba
    return cast(_JWTPayload, raw)


class _JWTPayload(TypedDict):
    """
    Structure of JWT payload decoded by jose.jwt.decode().
    
    Fields match the documented JWT structure:
    - sub: user_id as string (RFC 7519 subject claim)
    - role: user role value (private claim for authorization)
    - iat: issued at timestamp (UTC epoch)
    - exp: expires at timestamp (UTC epoch)
    """
    sub: str
    role: str
    iat: int
    exp: int


class JWTTokenIssuer:
    """
    Implementación de TokenIssuerPort con python-jose.

    Args:
        secret_key:        Clave HMAC. Mínimo 32 bytes aleatorios.
                           Genera con: openssl rand -hex 32
        expires_minutes:   Tiempo de vida del token en minutos. Default: 60.
    """

    def __init__(self, secret_key: str, expires_minutes: int = 60) -> None:
        if len(secret_key) < 32:
            raise ValueError(
                "SECRET_KEY debe tener al menos 32 caracteres. "
                "Genera una con: openssl rand -hex 32"
            )
        self._secret          = secret_key
        self._expires_minutes = expires_minutes

    def issue(self, user_id: uuid.UUID, role: UserRole) -> AccessToken:
        """
        Firma y devuelve un AccessToken listo para el cliente.
        Nunca lanza — los errores de configuración se detectan en __init__.
        """
        now    = datetime.now(timezone.utc)
        expiry = now + timedelta(minutes=self._expires_minutes)

        payload: dict[str, str | int] = {
            "sub":  str(user_id),
            "role": role.value,
            "iat":  int(now.timestamp()),
            "exp":  int(expiry.timestamp()),
        }

        token_str = jwt.encode(payload, self._secret, algorithm=_ALGORITHM)

        return AccessToken(
            value=token_str,
            expires_in=self._expires_minutes * 60,   # segundos, para el cliente
        )

    def decode(
        self, token: str
    ) -> Result[_JWTPayload, TokenExpiredError | TokenInvalidError]:
        """
        Verifica y decodifica un JWT.
        Usado por la dependencia get_current_user de FastAPI.

        Returns:
            Ok(payload)           → token válido.
            Err(TokenExpiredError) → expirado pero bien formado.
            Err(TokenInvalidError) → firma inválida, malformado o algoritmo inesperado.
        """
        try:
            raw_payload = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
                options={"require": ["sub", "role", "exp", "iat"]},
            )
            payload = _validate_payload(raw_payload)
            return Ok(payload)

        except ExpiredSignatureError:
            return Err(TokenExpiredError())

        except JWTError as exc:
            return Err(TokenInvalidError(detail=str(exc)))


__all__: list[str] = ["JWTTokenIssuer"]
