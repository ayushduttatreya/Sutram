# packages/core/sutram_core/middleware/auth.py
from __future__ import annotations
from typing import Any
from jose import jwt, JWTError, ExpiredSignatureError


class AuthError(Exception):
    """Raised when JWT validation fails."""

    def __init__(self, message: str, expired: bool = False) -> None:
        super().__init__(message)
        self.expired = expired


def get_jwt_secret() -> str:
    """Returns JWT secret from settings. Patchable in tests."""
    from sutram_core.settings import get_settings
    return get_settings().jwt_secret


def get_jwt_algorithm() -> str:
    """Returns JWT algorithm from settings. Patchable in tests."""
    from sutram_core.settings import get_settings
    return get_settings().jwt_algorithm


def decode_jwt(token: str, algorithm: str | None = None) -> dict[str, Any]:
    """Decode and validate a JWT. Returns claims dict.

    Uses algorithm from settings if not explicitly provided.
    Raises AuthError on any validation failure.
    AuthError.expired is True if the token has expired (vs forged/invalid).
    """
    try:
        secret = get_jwt_secret()
        alg = algorithm or get_jwt_algorithm()
        claims = jwt.decode(token, secret, algorithms=[alg])
        if "tenant_id" not in claims:
            raise AuthError("Missing tenant_id claim")
        if "exp" not in claims:
            raise AuthError("Missing exp claim")
        return claims
    except AuthError:
        raise
    except ExpiredSignatureError as e:
        raise AuthError("Token has expired", expired=True) from e
    except JWTError as e:
        raise AuthError(f"Invalid token: {e}") from e
