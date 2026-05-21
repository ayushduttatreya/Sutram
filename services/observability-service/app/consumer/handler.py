# services/observability-service/app/consumer/handler.py
"""Routes parsed events to the correct sinks: tail sampler, Prometheus, DB writes."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sutram_core.events.base import BaseEvent
from sutram_core.events.execution import (
    ExecutionCompletedEvent,
    ExecutionPausedEvent,
    ExecutionStartedEvent,
    StepCompletedEvent,
    StepFailedEvent,
)
from sutram_core.events.memory import MemorySearchedEvent, MemoryWrittenEvent

from app.metrics.prometheus import (
    record_execution_completed,
    record_execution_started,
    record_memory_searched,
    record_step_completed,
)
from app.models.orm import AuditLogORM, ExecutionTraceORM
from app.sampling.tail_sampler import TailSampler


class EventHandler:
    def __init__(self, sampler: TailSampler, session: AsyncSession) -> None:
        self._sampler = sampler
        self._session = session

    async def handle(self, event: BaseEvent, raw_data: dict[str, str]) -> None:
        if isinstance(event, ExecutionStartedEvent):
            await self._on_execution_started(event, raw_data)
        elif isinstance(event, StepCompletedEvent):
            await self._on_step_completed(event, raw_data)
        elif isinstance(event, StepFailedEvent):
            await self._on_step_failed(event, raw_data)
        elif isinstance(event, ExecutionCompletedEvent):
            await self._on_execution_completed(event)
        elif isinstance(event, ExecutionPausedEvent):
            await self._on_execution_paused(event)
        elif isinstance(event, MemoryWrittenEvent):
            await self._on_memory_written(event)
        elif isinstance(event, MemorySearchedEvent):
            await self._on_memory_searched(event)

    async def _on_execution_started(
        self, event: ExecutionStartedEvent, raw_data: dict[str, str]
    ) -> None:
        span_key = f"started:{event.execution_id}"
        await self._sampler.buffer_span(event.execution_id, span_key, raw_data)
        record_execution_started(tenant_id=str(event.tenant_id))
        await self._write_audit(
            tenant_id=event.tenant_id,
            action="execution.started",
            resource_id=event.execution_id,
        )

    async def _on_step_completed(self, event: StepCompletedEvent, raw_data: dict[str, str]) -> None:
        span_key = f"step:{event.step_index}"
        await self._sampler.buffer_span(event.execution_id, span_key, raw_data)
        record_step_completed(
            workflow_id=str(event.workflow_id),
            step_name=event.step_name,
            duration_ms=event.duration_ms,
        )

    async def _on_step_failed(self, event: StepFailedEvent, raw_data: dict[str, str]) -> None:
        span_key = f"step_failed:{event.step_index}"
        await self._sampler.buffer_span(event.execution_id, span_key, raw_data)
        await self._sampler.mark_has_failure(event.execution_id)
        await self._write_audit(
            tenant_id=event.tenant_id,
            action="execution.step.failed",
            resource_id=event.execution_id,
        )

    async def _on_execution_completed(self, event: ExecutionCompletedEvent) -> None:
        keep = await self._sampler.should_keep(
            event.execution_id, total_duration_ms=event.total_duration_ms
        )
        if keep:
            spans = await self._sampler.flush(event.execution_id)
            # Write the completion span itself
            trace = ExecutionTraceORM(
                trace_id=event.trace_id,
                execution_id=event.execution_id,
                tenant_id=event.tenant_id,
                workflow_id=event.workflow_id,
                event_type=event.event_type,
                duration_ms=event.total_duration_ms,
                cost_usd=event.total_cost_usd,
                status=event.status,
            )
            self._session.add(trace)
            # Write all buffered step spans
            for span_data in spans:
                self._write_span_from_dict(span_data, event.tenant_id, event.workflow_id)
            await self._session.flush()
        else:
            await self._sampler.flush(event.execution_id)  # discard buffer

        record_execution_completed(
            tenant_id=str(event.tenant_id),
            status=event.status,
            duration_ms=event.total_duration_ms,
            cost_usd=event.total_cost_usd,
        )
        await self._write_audit(
            tenant_id=event.tenant_id,
            action=f"execution.{event.status.lower()}",
            resource_id=event.execution_id,
        )

    async def _on_execution_paused(self, event: ExecutionPausedEvent) -> None:
        await self._write_audit(
            tenant_id=event.tenant_id,
            action="execution.paused",
            resource_id=event.execution_id,
        )

    async def _on_memory_written(self, event: MemoryWrittenEvent) -> None:
        await self._write_audit(
            tenant_id=event.tenant_id,
            action="memory.written",
            resource_id=event.memory_item_id,
        )

    async def _on_memory_searched(self, event: MemorySearchedEvent) -> None:
        record_memory_searched(latency_ms=event.latency_ms)

    def _write_span_from_dict(
        self,
        span_data: dict[str, str],
        tenant_id: uuid.UUID,
        workflow_id: uuid.UUID,
    ) -> None:
        """Reconstruct ExecutionTraceORM from a buffered raw span dict."""
        trace = ExecutionTraceORM(
            trace_id=uuid.UUID(span_data.get("trace_id", str(uuid.uuid4()))),
            execution_id=uuid.UUID(span_data.get("execution_id", str(uuid.uuid4()))),
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            event_type=span_data.get("event_type", "unknown"),
            step_name=span_data.get("step_name"),
            step_index=int(span_data["step_index"]) if "step_index" in span_data else None,
            duration_ms=int(span_data["duration_ms"]) if "duration_ms" in span_data else None,
            cost_usd=float(span_data["cost_usd"]) if "cost_usd" in span_data else None,
            error_type=span_data.get("error_type"),
            error_message=span_data.get("error_message"),
        )
        self._session.add(trace)

    async def _write_audit(
        self,
        tenant_id: uuid.UUID,
        action: str,
        resource_id: uuid.UUID | None = None,
    ) -> None:
        record = AuditLogORM(
            tenant_id=tenant_id,
            action=action,
            resource_id=resource_id,
        )
        self._session.add(record)
