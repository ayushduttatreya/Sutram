# services/observability-service/app/routes/audit.py
from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sutram_core.middleware.internal_auth import InternalAuthError, verify_internal_token
from app.dependencies import get_db_session
from app.models.orm import AuditLogORM
from app.settings import get_settings

router = APIRouter(tags=["audit"])
DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def _get_tenant(
    x_internal_token: str = Header(..., alias="X-Internal-Token"),
    x_tenant_id: uuid.UUID = Header(..., alias="X-Tenant-ID"),
) -> uuid.UUID:
    settings = get_settings()
    try:
        verify_internal_token(x_internal_token, settings.internal_auth_token)
    except InternalAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return x_tenant_id


TenantDep = Annotated[uuid.UUID, Depends(_get_tenant)]


@router.get("/audit-logs")
async def get_audit_logs(
    session: DBSession,
    tenant_id: TenantDep,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
) -> dict:
    settings = get_settings()
    effective_limit = min(limit, settings.audit_log_max_page_size)
    query = select(AuditLogORM).where(AuditLogORM.tenant_id == tenant_id)
    if action:
        query = query.where(AuditLogORM.action == action)
    query = query.order_by(AuditLogORM.timestamp.desc()).limit(effective_limit).offset(offset)
    result = await session.execute(query)
    records = result.scalars().all()
    return {
        "records": [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "action": r.action,
                "resource_id": str(r.resource_id) if r.resource_id else None,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in records
        ],
        "limit": effective_limit,
        "offset": offset,
    }
