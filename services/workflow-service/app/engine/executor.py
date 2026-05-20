"""Execution engine: acquires lock, guards terminal state, publishes events, updates status.

Core invariants:
1. Distributed lock held for entire execution lifetime (heartbeat renews TTL)
2. Checkpoints written BEFORE expensive steps (checkpoint_before=True)
3. Status transitions only via FSM — never set status directly
4. Both streams published on every event: 'executions' (global) and 'execution:{id}' (SSE)
5. On startup: if execution is already terminal (acks_late redelivery), raise and exit cleanly
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sutram_core.events.base import BaseEvent
from sutram_core.locking.redis_lock import RedisLock
from sutram_core.models.execution import ExecutionStatus
from sutram_core.streams.redis_streams import StreamProducer

from app.models.orm import WorkflowExecutionORM

_UNSET: object = object()

_TERMINAL_STATUSES = frozenset(
    {
        ExecutionStatus.COMPLETED.value,
        ExecutionStatus.FAILED.value,
        ExecutionStatus.CANCELLED.value,
    }
)


class ExecutionAlreadyTerminal(Exception):
    """Raised when a Celery task is redelivered after execution reached terminal state.

    With acks_late=True, Celery can redeliver a task if the worker crashes before
    acknowledging. The executor checks status on startup and exits cleanly if the
    execution already completed on a previous delivery.
    """


class Executor:
    """Drives a workflow execution from current state to completion, pause, or failure.

    Instantiate per execution run. Not safe to share across concurrent executions.
    """

    def __init__(
        self,
        session: AsyncSession,
        lock: RedisLock,
        stream_producer_global: StreamProducer,
        stream_producer_sse: StreamProducer,
        max_per_execution_usd: float = 10.0,
        max_per_day_usd: float = 100.0,
    ) -> None:
        self._session = session
        self._lock = lock
        self._producer_global = stream_producer_global
        self._producer_sse = stream_producer_sse
        self._max_per_execution = max_per_execution_usd
        self._max_per_day = max_per_day_usd

    @staticmethod
    def check_not_terminal(status: str) -> None:
        """Raise ExecutionAlreadyTerminal if execution is in a terminal state.

        Called at the start of every Celery task to guard against acks_late redelivery.
        """
        if status in _TERMINAL_STATUSES:
            raise ExecutionAlreadyTerminal(
                f"Execution is already in terminal state '{status}'. "
                "This appears to be a stale Celery redelivery (acks_late). Ignoring."
            )

    async def _publish(self, execution_id: uuid.UUID, event: BaseEvent) -> None:
        """Publish event to both the global stream and the per-execution SSE stream.

        Global stream: 'executions' — consumed by observability-service.
        Per-execution stream: 'execution:{id}' — consumed by SSE endpoint clients.
        """
        await self._producer_global.publish("executions", event)
        await self._producer_sse.publish(f"execution:{execution_id}", event)

    async def _update_status(
        self,
        execution_orm: WorkflowExecutionORM,
        new_status: ExecutionStatus,
        *,
        error_message: str | None = _UNSET,  # type: ignore[assignment]
        pause_reason: str | None = _UNSET,  # type: ignore[assignment]
    ) -> None:
        """Persist status change and heartbeat renewal via current session.

        Does NOT commit. The caller (executor loop) owns the surrounding transaction.
        Pass error_message=None or pause_reason=None to explicitly clear the column.
        Omit the keyword entirely to leave the column unchanged.
        """
        execution_orm.status = new_status.value
        execution_orm.last_heartbeat = datetime.now(UTC)
        if error_message is not _UNSET:
            execution_orm.error_message = error_message
        if pause_reason is not _UNSET:
            execution_orm.pause_reason = pause_reason
        await self._session.flush()
