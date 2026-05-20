import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.engine.recovery import RecoveryHandler
from sutram_core.locking.redis_lock import LockAcquisitionError


@pytest.mark.asyncio
async def test_recovery_skips_execution_with_active_lock():
    """If lock is held, another worker is alive — skip recovery."""
    mock_lock = MagicMock()
    mock_lock.acquire = MagicMock()
    # Simulate lock already held — context manager raises on __aenter__
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(side_effect=LockAcquisitionError("lock held"))
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_lock.acquire.return_value = ctx

    enqueue_fn = AsyncMock()
    handler = RecoveryHandler(lock=mock_lock, enqueue_fn=enqueue_fn)

    result = await handler.try_recover(uuid.uuid4())
    assert result is False
    enqueue_fn.assert_not_called()


@pytest.mark.asyncio
async def test_recovery_enqueues_when_lock_free():
    """If lock is free (worker is dead), re-enqueue the execution."""
    mock_lock = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value="token")
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_lock.acquire.return_value = ctx

    enqueue_fn = AsyncMock()
    handler = RecoveryHandler(lock=mock_lock, enqueue_fn=enqueue_fn)

    execution_id = uuid.uuid4()
    result = await handler.try_recover(execution_id)
    assert result is True
    enqueue_fn.assert_called_once_with(str(execution_id))


@pytest.mark.asyncio
async def test_run_forever_calls_get_stale_and_recover(monkeypatch):
    """run_forever should query for stale executions and call try_recover for each."""
    execution_ids = [uuid.uuid4(), uuid.uuid4()]
    call_count = 0

    async def mock_get_stale():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return execution_ids
        raise asyncio.CancelledError  # stop the loop after first iteration

    import asyncio

    mock_lock = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value="token")
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_lock.acquire.return_value = ctx

    enqueue_fn = AsyncMock()
    handler = RecoveryHandler(lock=mock_lock, enqueue_fn=enqueue_fn)

    with pytest.raises(asyncio.CancelledError):
        await handler.run_forever(mock_get_stale, interval_seconds=0)

    assert enqueue_fn.call_count == len(execution_ids)
