# app/tasks/recover.py
"""Celery beat task: scan for stale executions and re-enqueue them."""

from __future__ import annotations

import asyncio

from app.tasks.celery_app import celery_app


@celery_app.task(  # type: ignore[untyped-decorator]
    name="workflow.recover_stale_executions",
    bind=True,
    max_retries=0,
)
def recover_stale_executions(self: object) -> None:
    """Beat task: one recovery scan pass — detects stale executions and re-enqueues them."""
    asyncio.run(_run())


async def _run() -> None:
    from app.dependencies import get_db_session_context, get_redis_lock
    from app.engine.recovery import RecoveryHandler, get_stale_executions
    from app.tasks.execute import execute_workflow

    async def _enqueue(execution_id: str) -> None:
        execute_workflow.delay(execution_id=execution_id)

    lock = get_redis_lock()
    handler = RecoveryHandler(lock=lock, enqueue_fn=_enqueue)
    await handler.run_once(get_stale_executions)
