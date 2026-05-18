"""
auth/infrastructure/persistence/encryption.py
=============================================
TypeDecorator de SQLAlchemy que encripta/desencripta transparentemente
usando Fernet (AES-128-CBC + HMAC-SHA256).

Fernet garantiza:
  - Confidencialidad (encriptación simétrica).
  - Integridad (el token incluye HMAC; un valor alterado lanza InvalidToken).
  - Freshness opcional (los tokens tienen timestamp embebido).

Uso en ORM:
    access_token: Mapped[str] = mapped_column(EncryptedString(), nullable=False)

El valor se almacena en DB como texto base64 urlsafe.
En memoria siempre es el plaintext.
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator


# ---------------------------------------------------------------------------
# Clave Fernet
# ---------------------------------------------------------------------------

def _load_key() -> Fernet:
    """
    Carga la clave desde la variable de entorno TOKEN_ENCRYPTION_KEY.

    Genera una con:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    Nunca hardcodees la clave. En producción usa un secret manager.
    """
    raw = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
    if not raw:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY no está definida. "
            "Genera una con Fernet.generate_key() y agrégala al .env"
        )
    return Fernet(raw.encode())


# ---------------------------------------------------------------------------
# TypeDecorator
# ---------------------------------------------------------------------------

class EncryptedString(TypeDecorator):
    """
    Columna de texto que se encripta al escribir y se desencripta al leer.

    impl = String porque Fernet produce texto base64 urlsafe.
    cache_ok = True: el decorador es stateless (la clave viene del entorno).
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        """Plaintext → ciphertext antes de INSERT/UPDATE."""
        if value is None:
            return None
        fernet = _load_key()
        return fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:
        """Ciphertext → plaintext después de SELECT."""
        if value is None:
            return None
        fernet = _load_key()
        try:
            return fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            # Token corrupto o clave rotada sin re-encriptación previa.
            raise ValueError(
                "access_token corrupto o encriptado con clave diferente. "
                "Verifica TOKEN_ENCRYPTION_KEY y el proceso de rotación de claves."
            ) from exc


__all__: list[str] = ["EncryptedString"]