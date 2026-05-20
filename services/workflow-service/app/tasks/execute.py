# app/tasks/execute.py
"""Celery task: pick up a workflow execution and drive it to completion.

Design notes:
- max_retries=0: step-level retries are handled inside Executor, not by Celery.
  Celery retrying the whole task would bypass checkpoint recovery.
- acks_late=True + reject_on_worker_lost=True: if worker dies, task returns to queue.
  The recovery handler detects the stale heartbeat and re-enqueues; the second worker
  loads the latest checkpoint and resumes from there.
- ExecutionAlreadyTerminal: guards against acks_late redelivery after completion.
"""

from __future__ import annotations

import asyncio
import uuid

from celery import Task

from app.tasks.celery_app import celery_app


@celery_app.task(  # type: ignore[untyped-decorator]
    name="workflow.execute",
    bind=True,
    max_retries=0,
    acks_late=True,
    reject_on_worker_lost=True,
)
def execute_workflow(self: Task, execution_id: str) -> None:
    """Entry point for Celery workers. Runs async executor in a new event loop."""
    asyncio.run(_run(execution_id))


async def _run(execution_id: str) -> None:
    """Async implementation — separated so it can be tested without Celery infrastructure."""
    from sqlalchemy import select

    from app.dependencies import get_db_session_context, get_redis_lock, get_stream_producers
    from app.engine.executor import ExecutionAlreadyTerminal, Executor
    from app.models.orm import WorkflowExecutionORM

    async with get_db_session_context() as session:
        result = await session.execute(
            select(WorkflowExecutionORM).where(WorkflowExecutionORM.id == uuid.UUID(execution_id))
        )
        execution = result.scalar_one_or_none()
        if execution is None:
            return  # execution was deleted — nothing to do

        # Guard against acks_late redelivery on already-completed executions
        try:
            Executor.check_not_terminal(execution.status)
        except ExecutionAlreadyTerminal:
            return

        lock = get_redis_lock()
        global_producer, sse_producer = get_stream_producers()

        executor = Executor(
            session=session,
            lock=lock,
            stream_producer_global=global_producer,
            stream_producer_sse=sse_producer,
        )

        from sutram_core.models.execution import ExecutionStatus

        await executor._update_status(execution, ExecutionStatus.RUNNING)
