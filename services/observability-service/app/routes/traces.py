# services/observability-service/app/routes/traces.py
from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sutram_core.middleware.internal_auth import InternalAuthError, verify_internal_token
from app.dependencies import get_db_session
from app.models.orm import ExecutionTraceORM
from app.settings import get_settings

router = APIRouter(tags=["traces"])
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


@router.get("/traces/{execution_id}")
async def get_traces(
    execution_id: uuid.UUID,
    session: DBSession,
    tenant_id: TenantDep,
) -> dict:
    result = await session.execute(
        select(ExecutionTraceORM)
        .where(
            ExecutionTraceORM.execution_id == execution_id,
            ExecutionTraceORM.tenant_id == tenant_id,
        )
        .order_by(ExecutionTraceORM.start_time)
    )
    spans = result.scalars().all()
    return {
        "execution_id": str(execution_id),
        "spans": [
            {
                "id": str(s.id),
                "trace_id": str(s.trace_id),
                "event_type": s.event_type,
                "step_name": s.step_name,
                "step_index": s.step_index,
                "duration_ms": s.duration_ms,
                "cost_usd": s.cost_usd,
                "status": s.status,
                "error_type": s.error_type,
                "start_time": s.start_time.isoformat() if s.start_time else None,
            }
            for s in spans
        ],
    }
