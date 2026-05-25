"""Internal endpoints — not exposed through api-gateway.

These endpoints are called by other services (memory-service, observability-service)
using the X-Internal-Token header for authentication. The token is verified by
middleware (to be wired in a later task).

RLS note: internal endpoints bypass tenant RLS since they may be called without a
tenant context (e.g., fetching tenant settings to verify a new tenant_id).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sutram_core.middleware.internal_auth import InternalAuthError, verify_internal_token

from app.dependencies import get_db_session
from app.models.orm import TenantORM


async def _verify_internal(
    x_internal_token: str = Header(..., alias="X-Internal-Token"),  # noqa: B008
) -> None:
    from app.settings import get_settings

    settings = get_settings()
    try:
        verify_internal_token(x_internal_token, settings.internal_auth_token)
    except InternalAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


router = APIRouter(tags=["internal"], dependencies=[Depends(_verify_internal)])

DBSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: uuid.UUID,
    session: DBSession,
) -> dict[str, object]:
    """Return tenant settings for inter-service use.

    Called by memory-service and observability-service to resolve tenant limits.
    """
    result = await session.execute(select(TenantORM).where(TenantORM.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "settings": tenant.settings,
    }
