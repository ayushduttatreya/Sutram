"""Background recovery handler: detects stale executions and re-enqueues them.

Design:
- Runs as an asyncio background task inside the web process (NOT a Celery worker)
- Every `interval_seconds` (default 60): queries for RUNNING executions with stale heartbeat
- For each stale execution:
  - Try to acquire `execution:{id}:lock`
  - LockAcquisitionError → original worker is still alive, skip
  - Lock acquired → original worker is dead, re-enqueue via Celery, release lock immediately
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

        The lock is acquired and immediately released to confirm the worker is dead.
        Enqueueing happens AFTER lock release to avoid the new worker racing against
        the recovery handler's still-held lock.
        """
        try:
            async with self._lock.acquire(f"execution:{execution_id}:lock", ttl_seconds=30):
                pass  # confirms worker is dead; lock is released on context exit
        except LockAcquisitionError:
            return False
        # Lock is released — safe to enqueue without racing the new worker
        await self._enqueue(str(execution_id))
        return True

    async def run_forever(
        self,
        get_stale_executions: Callable[[], Awaitable[list[uuid.UUID]]],
        interval_seconds: int = 60,
    ) -> None:
        """Background loop: poll for stale executions and try to recover each one.

        Exceptions inside the loop are logged and swallowed to prevent the recovery
        handler from crashing the entire web process. asyncio.CancelledError propagates
        for graceful shutdown.
        """
        import logging

        logger = logging.getLogger(__name__)

        while True:
            try:
                stale = await get_stale_executions()
                for execution_id in stale:
                    await self.try_recover(execution_id)
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
