import uuid
from datetime import UTC, datetime

from app.consumer.dispatcher import UnknownEventType, parse_event
from sutram_core.events.execution import (
    ExecutionCompletedEvent,
    ExecutionStartedEvent,
    StepCompletedEvent,
    StepFailedEvent,
)
from sutram_core.events.memory import MemoryWrittenEvent


def make_stream_dict(event_type: str, **extra) -> dict[str, str]:
    return {
        "event_type": event_type,
        "trace_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "schema_version": "1",
        **{k: str(v) for k, v in extra.items()},
    }


def test_parses_execution_started():
    data = make_stream_dict(
        "execution.started",
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
    )
    event = parse_event(data)
    assert isinstance(event, ExecutionStartedEvent)
    assert event.event_type == "execution.started"


def test_parses_step_completed():
    data = make_stream_dict(
        "execution.step.completed",
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        step_name="fetch",
        step_index="0",
        duration_ms="500",
        cost_usd="0.05",
    )
    event = parse_event(data)
    assert isinstance(event, StepCompletedEvent)
    assert event.duration_ms == 500
    assert event.cost_usd == 0.05


def test_parses_step_failed():
    data = make_stream_dict(
        "execution.step.failed",
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        step_name="summarize",
        step_index="1",
        error_type="TimeoutError",
        error_message="LLM call timed out",
    )
    event = parse_event(data)
    assert isinstance(event, StepFailedEvent)


def test_parses_execution_completed():
    data = make_stream_dict(
        "execution.completed",
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        status="COMPLETED",
        total_duration_ms="12000",
        total_cost_usd="0.30",
        total_steps="3",
    )
    event = parse_event(data)
    assert isinstance(event, ExecutionCompletedEvent)
    assert event.total_duration_ms == 12000


def test_parses_memory_written():
    data = make_stream_dict(
        "memory.written",
        memory_item_id=uuid.uuid4(),
        memory_type="semantic",
    )
    event = parse_event(data)
    assert isinstance(event, MemoryWrittenEvent)


def test_unknown_event_type_raises():
    data = make_stream_dict("unknown.event.type")
    import pytest

    with pytest.raises(UnknownEventType):
        parse_event(data)
