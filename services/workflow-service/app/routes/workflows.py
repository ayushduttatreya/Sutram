# app/routes/workflows.py
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sutram_core.middleware.tenant import set_tenant_context

from app.dependencies import get_db_session, get_tenant_id_from_header
from app.models.orm import WorkflowORM
from app.schemas.workflows import CreateWorkflowRequest, WorkflowResponse

router = APIRouter(tags=["workflows"])

DBSession = Annotated[AsyncSession, Depends(get_db_session)]
TenantID = Annotated[uuid.UUID, Depends(get_tenant_id_from_header)]


@router.post("/workflows", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    body: CreateWorkflowRequest,
    session: DBSession,
    tenant_id: TenantID,
) -> WorkflowORM:
    await set_tenant_context(session, str(tenant_id))
    wf = WorkflowORM(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        definition=body.definition.model_dump(),
    )
    session.add(wf)
    await session.flush()
    return wf


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    session: DBSession,
    tenant_id: TenantID,
) -> WorkflowORM:
    await set_tenant_context(session, str(tenant_id))
    result = await session.execute(
        select(WorkflowORM).where(
            WorkflowORM.id == workflow_id,
            WorkflowORM.tenant_id == tenant_id,
        )
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf
