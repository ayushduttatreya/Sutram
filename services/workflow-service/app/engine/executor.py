"""Execution engine: acquires lock, guards terminal state, publishes events, updates status.

Core invariants:
1. Distributed lock held for entire execution lifetime (heartbeat renews TTL)
2. Checkpoints written BEFORE expensive steps (checkpoint_before=True)
3. Status transitions only via FSM — never set status directly
4. Both streams published on every event: 'executions' (global) and 'execution:{id}' (SSE)
5. On startup: if execution is already terminal (acks_late redelivery), raise and exit cleanly
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sutram_core.events.base import BaseEvent
from sutram_core.locking.redis_lock import LockAcquisitionError, RedisLock
from sutram_core.models.execution import ExecutionStatus
from sutram_core.streams.redis_streams import StreamProducer

from app.models.orm import WorkflowExecutionORM

_UNSET: object = object()
_logger = logging.getLogger(__name__)

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

    async def run(
        self,
        execution: WorkflowExecutionORM,
        workflow_definition: WorkflowDefinition,  # noqa: F821 — resolved via `from __future__ import annotations`
    ) -> None:
        """Drive the execution from PENDING to COMPLETED, PAUSED, or FAILED.

        Acquires a distributed lock for the entire duration. Returns silently if
        the lock is already held — another worker has this execution.
        """
        from sutram_core.models.execution import ExecutionContext

        from app.engine.checkpoint import CheckpointManager
        from app.engine.cost_tracker import CostLimitExceeded, CostTracker
        from app.engine.state_machine import ExecutionFSM
        from sutram_core.events.execution import (
            ExecutionCompletedEvent,
            ExecutionPausedEvent,
            ExecutionStartedEvent,
            StepCompletedEvent,
        )

        lock_key = f"execution:{execution.id}:lock"
        try:
            async with self._lock.acquire(lock_key, ttl_seconds=30):
                # --- Setup ---
                ctx = ExecutionContext.model_validate(execution.context)
                cost_tracker = CostTracker(
                    max_per_execution=self._max_per_execution,
                    max_per_day=self._max_per_day,
                )
                checkpoint_mgr = CheckpointManager(self._session)

                checkpoint = await checkpoint_mgr.get_latest(execution.id)
                if checkpoint is not None:
                    start_index = checkpoint.step_index + 1
                    ctx.variables = checkpoint.variables
                else:
                    start_index = 0

                # PENDING → RUNNING
                fsm = ExecutionFSM(ExecutionStatus(execution.status))
                fsm.transition("submit")
                run_start = time.monotonic()
                await self._update_status(execution, ExecutionStatus.RUNNING)
                await self._publish(
                    execution.id,
                    ExecutionStartedEvent(
                        tenant_id=execution.tenant_id,
                        execution_id=execution.id,
                        workflow_id=execution.workflow_id,
                    ),
                )
                await self._session.commit()

                # --- Step loop ---
                steps = workflow_definition.steps
                current_step_name = "unknown"
                try:
                    for i in range(start_index, len(steps)):
                        step = steps[i]
                        current_step_name = step.config.name

                        if checkpoint_mgr.should_checkpoint(step.config):
                            await checkpoint_mgr.write(
                                execution_id=execution.id,
                                tenant_id=execution.tenant_id,
                                step_name=step.config.name,
                                step_index=i,
                                variables=ctx.variables,
                            )
                            await self._session.commit()

                        step_start = time.monotonic()

                        # Simulated execution — no tool/LLM layer yet
                        step_cost = 0.0
                        step_outputs = {"simulated": True, "step": step.config.name}

                        cost_tracker.add(step_cost)

                        step_duration_ms = int((time.monotonic() - step_start) * 1000)
                        ctx.current_step_index = i + 1
                        ctx.total_cost_usd += step_cost
                        execution.context = ctx.model_dump(mode="json")

                        await self._publish(
                            execution.id,
                            StepCompletedEvent(
                                tenant_id=execution.tenant_id,
                                execution_id=execution.id,
                                workflow_id=execution.workflow_id,
                                step_name=step.config.name,
                                step_index=i,
                                duration_ms=step_duration_ms,
                                cost_usd=step_cost,
                                outputs=step_outputs,
                            ),
                        )
                        await self._session.flush()

                except CostLimitExceeded as exc:
                    _logger.warning(
                        "Cost limit exceeded for execution %s at step %s: %s",
                        execution.id,
                        current_step_name,
                        exc,
                    )
                    fsm.transition("cost_exceeded")
                    await self._update_status(
                        execution,
                        ExecutionStatus.PAUSED,
                        pause_reason="cost_limit_exceeded",
                    )
                    await self._publish(
                        execution.id,
                        ExecutionPausedEvent(
                            tenant_id=execution.tenant_id,
                            execution_id=execution.id,
                            workflow_id=execution.workflow_id,
                            pause_reason="cost_limit_exceeded",
                            paused_at_step=current_step_name,
                        ),
                    )
                    await self._session.commit()
                    return

                except Exception as exc:
                    _logger.exception(
                        "Unexpected error in execution %s at step %s",
                        execution.id,
                        current_step_name,
                    )
                    fsm.transition("error")
                    await self._update_status(
                        execution,
                        ExecutionStatus.PAUSED,
                        error_message=str(exc),
                    )
                    await self._publish(
                        execution.id,
                        ExecutionPausedEvent(
                            tenant_id=execution.tenant_id,
                            execution_id=execution.id,
                            workflow_id=execution.workflow_id,
                            pause_reason="error",
                            paused_at_step=current_step_name,
                        ),
                    )
                    await self._session.commit()
                    return

                # --- All steps done ---
                total_duration_ms = int((time.monotonic() - run_start) * 1000)
                fsm.transition("all_steps_done")
                await self._update_status(execution, ExecutionStatus.COMPLETED)
                await self._publish(
                    execution.id,
                    ExecutionCompletedEvent(
                        tenant_id=execution.tenant_id,
                        execution_id=execution.id,
                        workflow_id=execution.workflow_id,
                        status=ExecutionStatus.COMPLETED,
                        total_duration_ms=total_duration_ms,
                        total_cost_usd=cost_tracker.total,
                        total_steps=len(steps),
                    ),
                )
                await self._session.commit()

        except LockAcquisitionError:
            _logger.warning(
                "Could not acquire lock for execution %s — another worker is running it.",
                execution.id,
            )
