# app/routes/executions.py
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sutram_core.middleware.tenant import set_tenant_context
from sutram_core.models.execution import ExecutionContext, ExecutionStatus

from app.dependencies import get_db_session, get_redis_streams_for_sse, get_tenant_id_from_header
from app.engine.state_machine import ExecutionFSM, InvalidTransitionError
from app.models.orm import WorkflowExecutionORM, WorkflowORM
from app.schemas.workflows import ExecuteWorkflowRequest, ExecutionResponse

router = APIRouter(tags=["executions"])

DBSession = Annotated[AsyncSession, Depends(get_db_session)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis_streams_for_sse)]
TenantID = Annotated[uuid.UUID, Depends(get_tenant_id_from_header)]


@router.post("/workflows/{workflow_id}/execute", response_model=ExecutionResponse, status_code=202)
async def execute(
    workflow_id: uuid.UUID,
    body: ExecuteWorkflowRequest,
    session: DBSession,
    tenant_id: TenantID,
) -> WorkflowExecutionORM:
    await set_tenant_context(session, str(tenant_id))
    # Verify workflow exists
    wf_result = await session.execute(select(WorkflowORM).where(WorkflowORM.id == workflow_id))
    workflow_orm = wf_result.scalar_one_or_none()
    if workflow_orm is None:
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
        definition_snapshot=workflow_orm.definition,
    )
    session.add(execution)
    await session.flush()
    await session.commit()

    from app.tasks.execute import execute_workflow

    execute_workflow.delay(execution_id=str(exec_id))

    return execution


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: uuid.UUID,
    session: DBSession,
    tenant_id: TenantID,
) -> WorkflowExecutionORM:
    await set_tenant_context(session, str(tenant_id))
    result = await session.execute(
        select(WorkflowExecutionORM).where(
            WorkflowExecutionORM.id == execution_id,
            WorkflowExecutionORM.tenant_id == tenant_id,
        )
    )
    ex = result.scalar_one_or_none()
    if ex is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return ex


@router.post("/executions/{execution_id}/pause", response_model=ExecutionResponse)
async def pause_execution(
    execution_id: uuid.UUID,
    session: DBSession,
    tenant_id: TenantID,
) -> WorkflowExecutionORM:
    await set_tenant_context(session, str(tenant_id))
    result = await session.execute(
        select(WorkflowExecutionORM).where(
            WorkflowExecutionORM.id == execution_id,
            WorkflowExecutionORM.tenant_id == tenant_id,
        )
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
        raise HTTPException(status_code=409, detail=str(e)) from e
    return ex


@router.post("/executions/{execution_id}/resume", response_model=ExecutionResponse)
async def resume_execution(
    execution_id: uuid.UUID,
    session: DBSession,
    tenant_id: TenantID,
) -> WorkflowExecutionORM:
    await set_tenant_context(session, str(tenant_id))
    result = await session.execute(
        select(WorkflowExecutionORM).where(
            WorkflowExecutionORM.id == execution_id,
            WorkflowExecutionORM.tenant_id == tenant_id,
        )
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
        raise HTTPException(status_code=409, detail=str(e)) from e
    await session.commit()
    from app.tasks.execute import execute_workflow

    execute_workflow.delay(execution_id=str(execution_id))
    return ex


@router.post("/executions/{execution_id}/cancel", response_model=ExecutionResponse)
async def cancel_execution(
    execution_id: uuid.UUID,
    session: DBSession,
    tenant_id: TenantID,
) -> WorkflowExecutionORM:
    await set_tenant_context(session, str(tenant_id))
    result = await session.execute(
        select(WorkflowExecutionORM).where(
            WorkflowExecutionORM.id == execution_id,
            WorkflowExecutionORM.tenant_id == tenant_id,
        )
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
        raise HTTPException(status_code=409, detail=str(e)) from e
    return ex


@router.get("/executions/{execution_id}/stream")
async def stream_execution(
    execution_id: uuid.UUID,
    redis: RedisDep,
    tenant_id: TenantID,
) -> StreamingResponse:
    """SSE stream of execution events for real-time monitoring.

    Subscribes to the per-execution Redis Stream `execution:{id}` and yields
    events as Server-Sent Events. Closes when a terminal event is received
    or the client disconnects.
    """
    # Verify ownership before streaming
    from app.dependencies import get_db_session_context

    async with get_db_session_context() as check_session:
        r = await check_session.execute(
            select(WorkflowExecutionORM.id).where(
                WorkflowExecutionORM.id == execution_id,
                WorkflowExecutionORM.tenant_id == tenant_id,
            )
        )
        if r.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Execution not found")

    stream_key = f"execution:{execution_id}"
    group = "sse-stream-consumers"
    consumer_name = f"sse-{uuid.uuid4()}"

    # Create consumer group idempotently
    try:
        await redis.xgroup_create(stream_key, group, id="0", mkstream=True)
    except aioredis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

    async def event_generator():
        _TERMINAL = {"execution.completed", "execution.paused", "execution.failed"}
        try:
            while True:
                results = await redis.xreadgroup(
                    groupname=group,
                    consumername=consumer_name,
                    streams={stream_key: ">"},
                    count=10,
                    block=1000,
                )
                if not results:
                    continue
                for _stream, entries in results:
                    for msg_id, fields in entries:
                        decoded = {
                            k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
                            for k, v in fields.items()
                        }
                        await redis.xack(stream_key, group, msg_id)
                        yield f"event: {decoded.get('event_type', 'message')}\ndata: {json.dumps(decoded)}\n\n"
                        if decoded.get("event_type") in _TERMINAL:
                            return
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
