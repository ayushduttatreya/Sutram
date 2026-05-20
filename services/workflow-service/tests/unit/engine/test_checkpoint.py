import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.engine.checkpoint import CheckpointManager
from sutram_core.models.workflow import StepConfig


@pytest.mark.asyncio
async def test_should_checkpoint_true_when_config_says_so():
    session = AsyncMock()
    manager = CheckpointManager(session=session)
    step = StepConfig(name="llm_call", checkpoint_before=True)
    assert manager.should_checkpoint(step) is True


@pytest.mark.asyncio
async def test_should_checkpoint_false_when_config_says_no():
    session = AsyncMock()
    manager = CheckpointManager(session=session)
    step = StepConfig(name="cheap_step", checkpoint_before=False)
    assert manager.should_checkpoint(step) is False


@pytest.mark.asyncio
async def test_write_adds_checkpoint_orm_to_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    manager = CheckpointManager(session=session)
    execution_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    await manager.write(
        execution_id=execution_id,
        tenant_id=tenant_id,
        step_name="fetch_sources",
        step_index=2,
        variables={"results": ["a", "b"]},
    )

    assert session.add.called
    orm_arg = session.add.call_args[0][0]
    assert orm_arg.execution_id == execution_id
    assert orm_arg.step_name == "fetch_sources"
    assert orm_arg.step_index == 2
    assert orm_arg.variables == {"results": ["a", "b"]}
    assert orm_arg.schema_version == 1
    assert orm_arg.tenant_id == tenant_id
    assert orm_arg.state == {}  # default when state=None is passed
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_write_returns_checkpoint_orm():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    manager = CheckpointManager(session=session)

    result = await manager.write(
        execution_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        step_name="step1",
        step_index=0,
        variables={},
    )

    from app.models.orm import CheckpointORM

    assert isinstance(result, CheckpointORM)


@pytest.mark.asyncio
async def test_get_latest_returns_none_when_no_checkpoints():
    from unittest.mock import MagicMock

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    manager = CheckpointManager(session=session)
    result = await manager.get_latest(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_latest_returns_checkpoint_when_found():
    from unittest.mock import MagicMock

    from app.models.orm import CheckpointORM

    session = AsyncMock()
    fake_checkpoint = MagicMock(spec=CheckpointORM)
    fake_checkpoint.step_index = 3
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_checkpoint
    session.execute = AsyncMock(return_value=mock_result)

    manager = CheckpointManager(session=session)
    result = await manager.get_latest(uuid.uuid4())
    assert result is fake_checkpoint
    assert result.step_index == 3
