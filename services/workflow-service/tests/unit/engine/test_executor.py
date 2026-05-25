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


# ---------------------------------------------------------------------------
# Tests for Executor.run()
# ---------------------------------------------------------------------------


def make_workflow_definition(n_steps: int = 2, checkpoint_before: bool = False):
    from sutram_core.models.workflow import StepConfig, WorkflowDefinition, WorkflowStep

    steps = [
        WorkflowStep(config=StepConfig(name=f"step_{i}", checkpoint_before=checkpoint_before))
        for i in range(n_steps)
    ]
    return WorkflowDefinition(steps=steps)


def make_lock_mock():
    from sutram_core.locking.redis_lock import RedisLock

    lock = MagicMock(spec=RedisLock)
    lock.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value="token"),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    return lock


@pytest.mark.asyncio
async def test_run_completes_execution_with_correct_status():
    """Happy path: all steps complete, execution transitions to COMPLETED."""
    from unittest.mock import patch

    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    lock = make_lock_mock()
    execution = make_mock_execution(ExecutionStatus.PENDING)

    with patch("app.engine.checkpoint.CheckpointManager.get_latest", new=AsyncMock(return_value=None)), \
         patch("app.engine.checkpoint.CheckpointManager.write", new=AsyncMock()):
        executor = make_executor(session=session, lock=lock)
        await executor.run(execution, make_workflow_definition(n_steps=2))

    assert execution.status == ExecutionStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_run_publishes_started_and_completed_events():
    """ExecutionStartedEvent and ExecutionCompletedEvent are published."""
    from unittest.mock import patch

    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    lock = make_lock_mock()
    global_producer = AsyncMock()
    global_producer.publish = AsyncMock()
    sse_producer = AsyncMock()
    sse_producer.publish = AsyncMock()
    execution = make_mock_execution(ExecutionStatus.PENDING)

    with patch("app.engine.checkpoint.CheckpointManager.get_latest", new=AsyncMock(return_value=None)), \
         patch("app.engine.checkpoint.CheckpointManager.write", new=AsyncMock()):
        executor = make_executor(
            session=session,
            lock=lock,
            producer_global=global_producer,
            producer_sse=sse_producer,
        )
        await executor.run(execution, make_workflow_definition(n_steps=1))

    published_types = [call.args[1].event_type for call in global_producer.publish.call_args_list]
    assert "execution.started" in published_types
    assert "execution.completed" in published_types


@pytest.mark.asyncio
async def test_run_writes_checkpoint_when_checkpoint_before_true():
    """For steps with checkpoint_before=True, CheckpointManager.write is called."""
    from unittest.mock import patch

    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    lock = make_lock_mock()
    execution = make_mock_execution(ExecutionStatus.PENDING)

    mock_write = AsyncMock()
    with patch("app.engine.checkpoint.CheckpointManager.get_latest", new=AsyncMock(return_value=None)), \
         patch("app.engine.checkpoint.CheckpointManager.write", new=mock_write):
        executor = make_executor(session=session, lock=lock)
        await executor.run(execution, make_workflow_definition(n_steps=2, checkpoint_before=True))

    assert mock_write.call_count == 2


@pytest.mark.asyncio
async def test_run_resumes_from_checkpoint_on_restart():
    """If a checkpoint exists at step_index=1, execution starts from step 2."""
    from unittest.mock import patch

    from app.models.orm import CheckpointORM
    from sutram_core.events.execution import StepCompletedEvent

    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    lock = make_lock_mock()
    execution = make_mock_execution(ExecutionStatus.PENDING)

    checkpoint = MagicMock(spec=CheckpointORM)
    checkpoint.step_index = 1
    checkpoint.variables = {}

    global_producer = AsyncMock()
    global_producer.publish = AsyncMock()
    sse_producer = AsyncMock()
    sse_producer.publish = AsyncMock()

    with patch("app.engine.checkpoint.CheckpointManager.get_latest", new=AsyncMock(return_value=checkpoint)), \
         patch("app.engine.checkpoint.CheckpointManager.write", new=AsyncMock()):
        executor = make_executor(
            session=session,
            lock=lock,
            producer_global=global_producer,
            producer_sse=sse_producer,
        )
        await executor.run(execution, make_workflow_definition(n_steps=3))

    step_completed_calls = [
        call.args[1]
        for call in global_producer.publish.call_args_list
        if isinstance(call.args[1], StepCompletedEvent)
    ]
    assert len(step_completed_calls) == 1
    assert step_completed_calls[0].step_name == "step_2"


@pytest.mark.asyncio
async def test_run_pauses_on_cost_exceeded():
    """When cost limit is exceeded, execution transitions to PAUSED."""
    from unittest.mock import patch

    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    lock = make_lock_mock()
    execution = make_mock_execution(ExecutionStatus.PENDING)

    with patch("app.engine.checkpoint.CheckpointManager.get_latest", new=AsyncMock(return_value=None)), \
         patch("app.engine.checkpoint.CheckpointManager.write", new=AsyncMock()):
        executor = make_executor(session=session, lock=lock)
        executor._max_per_execution = -1.0  # 0.0 > -1.0 triggers CostLimitExceeded
        await executor.run(execution, make_workflow_definition(n_steps=2))

    assert execution.status == ExecutionStatus.PAUSED.value
    assert execution.pause_reason == "cost_limit_exceeded"


@pytest.mark.asyncio
async def test_run_returns_if_lock_already_held():
    """If LockAcquisitionError is raised, run() returns without changing state."""
    from sutram_core.locking.redis_lock import LockAcquisitionError

    session = AsyncMock()
    session.commit = AsyncMock()
    lock = MagicMock()
    lock.acquire = MagicMock(side_effect=LockAcquisitionError("locked"))
    execution = make_mock_execution(ExecutionStatus.PENDING)
    original_status = execution.status

    executor = make_executor(session=session, lock=lock)
    await executor.run(execution, make_workflow_definition(n_steps=2))

    assert execution.status == original_status
    session.commit.assert_not_called()
