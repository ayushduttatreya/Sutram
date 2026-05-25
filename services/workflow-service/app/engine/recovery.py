"""Background recovery handler: detects stale executions and re-enqueues them.

Design:
- Runs as a Celery beat task (workflow.recover_stale_executions) every 60 seconds.
- For each stale RUNNING execution:
  - Try to acquire `execution:{id}:lock`
  - LockAcquisitionError → original worker is still alive, skip
  - Lock acquired → worker is dead; enqueue via Celery WHILE holding the lock to
    prevent concurrent recovery pods from double-enqueueing the same execution.
- RLS bypass requirement: this handler must query across ALL tenants.
  In development, the superuser role bypasses RLS. In production, use a SECURITY DEFINER
  function or connect with a role that has BYPASSRLS privilege.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable

from sutram_core.locking.redis_lock import LockAcquisitionError, RedisLock


class RecoveryHandler:
    """Detects and re-enqueues workflow executions whose worker has gone silent."""

    def __init__(
        self,
        lock: RedisLock,
        enqueue_fn: Callable[[str], Awaitable[None]],
    ) -> None:
        self._lock = lock
        self._enqueue = enqueue_fn

    async def try_recover(self, execution_id: uuid.UUID) -> bool:
        """Attempt recovery of a stale execution.

        Returns True if re-enqueued (worker was dead).
        Returns False if lock is held (worker is still alive).

        The lock is held during enqueue to prevent a concurrent recovery pod from
        also acquiring the lock and double-enqueueing the same execution.
        """
        try:
            async with self._lock.acquire(f"execution:{execution_id}:lock", ttl_seconds=30):
                # Worker is dead (lock acquired). Enqueue while holding the lock
                # so no other recovery pod can race us and enqueue a duplicate.
                await self._enqueue(str(execution_id))
        except LockAcquisitionError:
            return False
        return True

    async def run_once(
        self,
        get_stale_executions: Callable[[], Awaitable[list[uuid.UUID]]],
    ) -> None:
        """Single recovery scan: query for stale executions and try to recover each one.

        Called by the Celery beat task every 60 seconds. Exceptions are logged and
        re-raised so the beat task can report failure.
        """
        stale = await get_stale_executions()
        for execution_id in stale:
            await self.try_recover(execution_id)

    async def run_forever(
        self,
        get_stale_executions: Callable[[], Awaitable[list[uuid.UUID]]],
        interval_seconds: int = 60,
    ) -> None:
        """Background loop: poll for stale executions and try to recover each one.

        Deprecated: prefer the Celery beat task (run_once). Kept for local dev/testing.
        Exceptions inside the loop are logged and swallowed. asyncio.CancelledError
        propagates for graceful shutdown.
        """
        import logging

        logger = logging.getLogger(__name__)

        while True:
            try:
                await self.run_once(get_stale_executions)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("Recovery handler error (will retry): %s", e, exc_info=True)
            await asyncio.sleep(interval_seconds)


async def get_stale_executions() -> list[uuid.UUID]:
    """Query for RUNNING executions with a stale heartbeat (worker likely dead).

    Uses the service's own DB session. No tenant context needed — this is a
    cross-tenant administrative query (superuser bypasses RLS by design here).
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.dependencies import get_db_session_context
    from app.models.orm import WorkflowExecutionORM
    from app.settings import get_settings

    settings = get_settings()
    threshold_minutes = settings.execution_stale_threshold_minutes
    cutoff = datetime.now(UTC) - timedelta(minutes=threshold_minutes)

    async with get_db_session_context() as session:
        result = await session.execute(
            select(WorkflowExecutionORM.id).where(
                WorkflowExecutionORM.status == "RUNNING",
                WorkflowExecutionORM.last_heartbeat < cutoff,
            )
        )
        return [row[0] for row in result]
