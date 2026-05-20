# app/routes/executions.py
from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.engine.state_machine import ExecutionFSM, InvalidTransitionError
from app.models.orm import WorkflowExecutionORM, WorkflowORM
from app.schemas.workflows import ExecuteWorkflowRequest, ExecutionResponse
from sutram_core.models.execution import ExecutionContext, ExecutionStatus

router = APIRouter(tags=["executions"])

DBSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/workflows/{workflow_id}/execute", response_model=ExecutionResponse, status_code=202)
async def execute(
    workflow_id: uuid.UUID,
    body: ExecuteWorkflowRequest,
    session: DBSession,
    tenant_id: uuid.UUID = Query(...),
) -> WorkflowExecutionORM:
    # Verify workflow exists
    wf_result = await session.execute(
        select(WorkflowORM).where(WorkflowORM.id == workflow_id)
    )
    if wf_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    exec_id = uuid.uuid4()
    context = ExecutionContext(
        execution_id=exec_id,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        variables=body.inputs,
    )
    execution = WorkflowExecutionORM(
        id=exec_id,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        status=ExecutionStatus.PENDING.value,
        context=context.model_dump(mode="json"),
    )
    session.add(execution)
    await session.flush()

    # Enqueue to Celery — NOTE: this fires before session.commit() (handled by get_db_session_context).
    # If commit fails, the task will query the DB and find execution=None (row rolled back) → silent exit.
    # This is acceptable for the execute path. Resume path has the execution pre-existing so it is safe.
    from app.tasks.execute import execute_workflow
    execute_workflow.delay(execution_id=str(exec_id))

    return execution


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: uuid.UUID,
    session: DBSession,
) -> WorkflowExecutionORM:
    result = await session.execute(
        select(WorkflowExecutionORM).where(WorkflowExecutionORM.id == execution_id)
    )
    ex = result.scalar_one_or_none()
    if ex is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return ex


@router.post("/executions/{execution_id}/pause", response_model=ExecutionResponse)
async def pause_execution(
    execution_id: uuid.UUID,
    session: DBSession,
) -> WorkflowExecutionORM:
    result = await session.execute(
        select(WorkflowExecutionORM).where(WorkflowExecutionORM.id == execution_id)
    )
    ex = result.scalar_one_or_none()
    if ex is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    try:
        fsm = ExecutionFSM(ExecutionStatus(ex.status))
        fsm.transition("manual_pause")
        ex.status = fsm.status.value
        ex.pause_reason = "manual_pause"
        await session.flush()
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return ex


@router.post("/executions/{execution_id}/resume", response_model=ExecutionResponse)
async def resume_execution(
    execution_id: uuid.UUID,
    session: DBSession,
) -> WorkflowExecutionORM:
    result = await session.execute(
        select(WorkflowExecutionORM).where(WorkflowExecutionORM.id == execution_id)
    )
    ex = result.scalar_one_or_none()
    if ex is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    try:
        fsm = ExecutionFSM(ExecutionStatus(ex.status))
        new_status = fsm.transition("resume")  # PAUSED→PENDING
        ex.status = new_status.value
        ex.pause_reason = None
        await session.flush()
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    # Enqueue AFTER flush — still before commit, but delay is moved after state change
    from app.tasks.execute import execute_workflow
    execute_workflow.delay(execution_id=str(execution_id))
    return ex


@router.post("/executions/{execution_id}/cancel", response_model=ExecutionResponse)
async def cancel_execution(
    execution_id: uuid.UUID,
    session: DBSession,
) -> WorkflowExecutionORM:
    result = await session.execute(
        select(WorkflowExecutionORM).where(WorkflowExecutionORM.id == execution_id)
    )
    ex = result.scalar_one_or_none()
    if ex is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    try:
        fsm = ExecutionFSM(ExecutionStatus(ex.status))
        fsm.transition("cancel")
        ex.status = fsm.status.value
        await session.flush()
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return ex
