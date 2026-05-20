# app/routes/workflows.py
from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.orm import WorkflowORM
from app.schemas.workflows import CreateWorkflowRequest, WorkflowResponse

router = APIRouter(tags=["workflows"])

DBSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/workflows", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    body: CreateWorkflowRequest,
    session: DBSession,
    tenant_id: uuid.UUID = Query(..., description="Tenant ID from auth middleware"),
) -> WorkflowORM:
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
) -> WorkflowORM:
    result = await session.execute(
        select(WorkflowORM).where(WorkflowORM.id == workflow_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf
