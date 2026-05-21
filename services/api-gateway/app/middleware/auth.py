# services/api-gateway/app/middleware/auth.py
"""JWT authentication dependency for the API gateway.

Extracts tenant_id from a Bearer JWT. Raises HTTPException on any auth failure.
Does NOT use set_tenant_context — no DB session exists in the gateway.
tenant_id is forwarded downstream as X-Tenant-ID header (handled in proxy.py).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, cast

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sutram_core.middleware.auth import AuthError

from app.settings import get_settings

_bearer = HTTPBearer(auto_error=False)


def _decode_jwt(token: str, secret: str, algorithm: str) -> dict[str, Any]:
    """Decode and validate a JWT using the provided secret and algorithm.

    Wraps jose errors in AuthError for consistent handling.
    """
    try:
        claims: dict[str, Any] = cast(
            dict[str, Any], jwt.decode(token, secret, algorithms=[algorithm])
        )
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


async def get_tenant_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
) -> uuid.UUID:
    """FastAPI dependency: verify JWT and return tenant_id as UUID.

    Returns 401 on missing, invalid, or expired token.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="missing_token")

    settings = get_settings()
    try:
        claims = _decode_jwt(credentials.credentials, settings.jwt_secret, settings.jwt_algorithm)
    except AuthError as e:
        detail = "token_expired" if e.expired else "invalid_token"
        raise HTTPException(status_code=401, detail=detail) from e

    try:
        return uuid.UUID(claims["tenant_id"])
    except ValueError as e:
        raise HTTPException(status_code=401, detail="invalid_token") from e


# Typed alias — use in route signatures: `tenant_id: AuthDep`
AuthDep = Annotated[uuid.UUID, Depends(get_tenant_id)]
