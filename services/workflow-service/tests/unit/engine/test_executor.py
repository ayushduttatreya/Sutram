import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.engine.executor import ExecutionAlreadyTerminal, Executor
from sutram_core.models.execution import ExecutionStatus


def make_mock_execution(status: ExecutionStatus = ExecutionStatus.PENDING):
    from app.models.orm import WorkflowExecutionORM

    orm = MagicMock(spec=WorkflowExecutionORM)
    orm.id = uuid.uuid4()
    orm.tenant_id = uuid.uuid4()
    orm.workflow_id = uuid.uuid4()
    orm.status = status.value
    orm.context = {
        "execution_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "workflow_id": str(uuid.uuid4()),
        "variables": {},
        "current_step_index": 0,
        "total_cost_usd": 0.0,
        "llm_calls": 0,
    }
    orm.error_message = None
    orm.pause_reason = None
    orm.last_heartbeat = None
    return orm


def make_executor(session=None, lock=None, producer_global=None, producer_sse=None):
    from sutram_core.locking.redis_lock import RedisLock
    from sutram_core.streams.redis_streams import StreamProducer

    return Executor(
        session=session or AsyncMock(),
        lock=lock or MagicMock(spec=RedisLock),
        stream_producer_global=producer_global or AsyncMock(spec=StreamProducer),
        stream_producer_sse=producer_sse or AsyncMock(spec=StreamProducer),
    )


# Terminal status guard tests
def test_check_not_terminal_passes_for_pending():
    Executor.check_not_terminal(ExecutionStatus.PENDING.value)  # no raise


def test_check_not_terminal_passes_for_running():
    Executor.check_not_terminal(ExecutionStatus.RUNNING.value)  # no raise


def test_check_not_terminal_raises_for_completed():
    with pytest.raises(ExecutionAlreadyTerminal):
        Executor.check_not_terminal(ExecutionStatus.COMPLETED.value)


def test_check_not_terminal_raises_for_failed():
    with pytest.raises(ExecutionAlreadyTerminal):
        Executor.check_not_terminal(ExecutionStatus.FAILED.value)


def test_check_not_terminal_raises_for_cancelled():
    with pytest.raises(ExecutionAlreadyTerminal):
        Executor.check_not_terminal(ExecutionStatus.CANCELLED.value)


# Publish tests
@pytest.mark.asyncio
async def test_publish_sends_to_both_streams():
    global_producer = AsyncMock()
    global_producer.publish = AsyncMock()
    sse_producer = AsyncMock()
    sse_producer.publish = AsyncMock()

    executor = make_executor(producer_global=global_producer, producer_sse=sse_producer)

    from sutram_core.events.execution import ExecutionStartedEvent

    event = ExecutionStartedEvent(
        tenant_id=uuid.uuid4(),
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
    )
    execution_id = uuid.uuid4()
    await executor._publish(execution_id, event)

    global_producer.publish.assert_called_once_with("executions", event)
    sse_producer.publish.assert_called_once_with(f"execution:{execution_id}", event)


# Status update tests
@pytest.mark.asyncio
async def test_update_status_sets_status_and_heartbeat():
    session = AsyncMock()
    session.flush = AsyncMock()

    executor = make_executor(session=session)
    execution = make_mock_execution(ExecutionStatus.PENDING)

    await executor._update_status(execution, ExecutionStatus.RUNNING)

    assert execution.status == ExecutionStatus.RUNNING.value
    assert execution.last_heartbeat is not None
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_status_sets_error_message():
    session = AsyncMock()
    session.flush = AsyncMock()

    executor = make_executor(session=session)
    execution = make_mock_execution(ExecutionStatus.RUNNING)

    await executor._update_status(execution, ExecutionStatus.FAILED, error_message="step failed")

    assert execution.status == ExecutionStatus.FAILED.value
    assert execution.error_message == "step failed"


@pytest.mark.asyncio
async def test_update_status_sets_pause_reason():
    session = AsyncMock()
    session.flush = AsyncMock()

    executor = make_executor(session=session)
    execution = make_mock_execution(ExecutionStatus.RUNNING)

    await executor._update_status(
        execution, ExecutionStatus.PAUSED, pause_reason="cost_limit_exceeded"
    )

    assert execution.status == ExecutionStatus.PAUSED.value
    assert execution.pause_reason == "cost_limit_exceeded"


@pytest.mark.asyncio
async def test_update_status_clears_pause_reason_when_passed_none():
    """Resuming an execution (PAUSED→RUNNING) should clear pause_reason to None."""
    session = AsyncMock()
    session.flush = AsyncMock()

    executor = make_executor(session=session)
    execution = make_mock_execution(ExecutionStatus.PAUSED)
    execution.pause_reason = "cost_limit_exceeded"

    await executor._update_status(execution, ExecutionStatus.RUNNING, pause_reason=None)

    assert execution.status == ExecutionStatus.RUNNING.value
    assert execution.pause_reason is None  # explicitly cleared


@pytest.mark.asyncio
async def test_update_status_leaves_pause_reason_unchanged_when_not_passed():
    """Not passing pause_reason should leave the existing value intact."""
    session = AsyncMock()
    session.flush = AsyncMock()

    executor = make_executor(session=session)
    execution = make_mock_execution(ExecutionStatus.PAUSED)
    execution.pause_reason = "error"

    await executor._update_status(execution, ExecutionStatus.RUNNING)  # no pause_reason kwarg

    assert execution.pause_reason == "error"  # unchanged
