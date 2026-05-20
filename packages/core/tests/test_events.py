import pytest
import uuid
from datetime import datetime
from sutram_core.events.execution import (
    ExecutionStartedEvent,
    StepCompletedEvent,
    StepFailedEvent,
    ExecutionCompletedEvent,
    ExecutionPausedEvent,
)
from sutram_core.events.memory import MemoryWrittenEvent, MemorySearchedEvent


def test_execution_started_event_fields():
    tenant_id = uuid.uuid4()
    execution_id = uuid.uuid4()
    event = ExecutionStartedEvent(
        tenant_id=tenant_id,
        execution_id=execution_id,
        workflow_id=uuid.uuid4(),
    )
    assert event.event_type == "execution.started"
    assert isinstance(event.trace_id, uuid.UUID)
    assert isinstance(event.timestamp, datetime)
    assert event.schema_version == 1


def test_step_completed_event_has_cost():
    event = StepCompletedEvent(
        tenant_id=uuid.uuid4(),
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        step_name="fetch_sources",
        step_index=0,
        duration_ms=1200,
        cost_usd=0.05,
    )
    assert event.event_type == "execution.step.completed"
    assert event.cost_usd == 0.05


def test_memory_written_event():
    event = MemoryWrittenEvent(
        tenant_id=uuid.uuid4(),
        memory_item_id=uuid.uuid4(),
        memory_type="semantic",
    )
    assert event.event_type == "memory.written"


def test_base_event_to_stream_dict_serializes_to_strings():
    event = ExecutionStartedEvent(
        tenant_id=uuid.uuid4(),
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
    )
    d = event.to_stream_dict()
    # All values must be strings (Redis Streams requirement)
    for k, v in d.items():
        assert isinstance(v, str), f"Key {k} has non-string value: {type(v)}"


def test_two_events_have_different_trace_ids():
    e1 = ExecutionStartedEvent(
        tenant_id=uuid.uuid4(), execution_id=uuid.uuid4(), workflow_id=uuid.uuid4()
    )
    e2 = ExecutionStartedEvent(
        tenant_id=uuid.uuid4(), execution_id=uuid.uuid4(), workflow_id=uuid.uuid4()
    )
    assert e1.trace_id != e2.trace_id


import json
from sutram_core.models.execution import ExecutionStatus
from sutram_core.models.memory import MemoryType


def test_to_stream_dict_nested_outputs_is_valid_json():
    event = StepCompletedEvent(
        tenant_id=uuid.uuid4(),
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        step_name="summarize",
        step_index=1,
        duration_ms=500,
        outputs={"tokens": 42, "answer": "yes"},
    )
    d = event.to_stream_dict()
    parsed = json.loads(d["outputs"])
    assert parsed == {"tokens": 42, "answer": "yes"}


def test_event_type_is_immutable():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ExecutionStartedEvent(
            tenant_id=uuid.uuid4(),
            execution_id=uuid.uuid4(),
            workflow_id=uuid.uuid4(),
            event_type="execution.CORRUPTED",
        )


def test_execution_completed_event_rejects_invalid_status():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ExecutionCompletedEvent(
            tenant_id=uuid.uuid4(),
            execution_id=uuid.uuid4(),
            workflow_id=uuid.uuid4(),
            status="oops",
            total_duration_ms=1000,
            total_cost_usd=0.5,
            total_steps=3,
        )


def test_memory_written_event_rejects_invalid_type():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        MemoryWrittenEvent(
            tenant_id=uuid.uuid4(),
            memory_item_id=uuid.uuid4(),
            memory_type="not_a_valid_type",
        )


def test_execution_completed_event_accepts_valid_status():
    event = ExecutionCompletedEvent(
        tenant_id=uuid.uuid4(),
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        status=ExecutionStatus.COMPLETED,
        total_duration_ms=1000,
        total_cost_usd=0.5,
        total_steps=3,
    )
    assert event.status == ExecutionStatus.COMPLETED
