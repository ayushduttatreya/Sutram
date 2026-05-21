# services/observability-service/app/routes/metrics_api.py
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sutram_core.middleware.internal_auth import InternalAuthError, verify_internal_token

from app.dependencies import get_db_session
from app.models.orm import ExecutionTraceORM
from app.settings import get_settings

router = APIRouter(tags=["metrics"])
DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def _get_tenant(
    x_internal_token: str = Header(..., alias="X-Internal-Token"),  # noqa: B008
    x_tenant_id: uuid.UUID = Header(..., alias="X-Tenant-ID"),  # noqa: B008
) -> uuid.UUID:
    settings = get_settings()
    try:
        verify_internal_token(x_internal_token, settings.internal_auth_token)
    except InternalAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return x_tenant_id


TenantDep = Annotated[uuid.UUID, Depends(_get_tenant)]


@router.get("/metrics")
async def get_metrics_summary(
    session: DBSession,
    tenant_id: TenantDep,
) -> dict[str, Any]:
    result = await session.execute(
        select(
            ExecutionTraceORM.status,
            func.count().label("count"),
            func.sum(ExecutionTraceORM.cost_usd).label("total_cost"),
            func.avg(ExecutionTraceORM.duration_ms).label("avg_duration_ms"),
        )
        .where(
            ExecutionTraceORM.tenant_id == tenant_id,
            ExecutionTraceORM.event_type == "execution.completed",
        )
        .group_by(ExecutionTraceORM.status)
    )
    rows = result.all()
    return {
        "tenant_id": str(tenant_id),
        "executions_by_status": [
            {
                "status": row.status,
                "count": row.count,
                "total_cost_usd": float(row.total_cost or 0),
                "avg_duration_ms": float(row.avg_duration_ms or 0),
            }
            for row in rows
        ],
    }
