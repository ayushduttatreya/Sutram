import pytest
import asyncio
import uuid
from sutram_core.locking.redis_lock import RedisLock, LockAcquisitionError


@pytest.mark.asyncio
async def test_lock_acquire_and_release(fake_redis):
    lock = RedisLock(redis=fake_redis)
    key = f"execution:{uuid.uuid4()}:lock"

    async with lock.acquire(key, ttl_seconds=30):
        val = await fake_redis.get(key)
        assert val is not None

    # After context exit, lock is released
    val = await fake_redis.get(key)
    assert val is None


@pytest.mark.asyncio
async def test_second_acquire_raises_when_locked(fake_redis):
    lock = RedisLock(redis=fake_redis)
    key = f"execution:{uuid.uuid4()}:lock"

    async with lock.acquire(key, ttl_seconds=30):
        with pytest.raises(LockAcquisitionError):
            async with lock.acquire(key, ttl_seconds=30):
                pass


@pytest.mark.asyncio
async def test_lock_expires_after_ttl(fake_redis):
    lock = RedisLock(redis=fake_redis)
    key = f"execution:{uuid.uuid4()}:lock"

    # Set a key with 100ms TTL, sleep 300ms to ensure expiry
    await fake_redis.set(key, "old-owner", px=100)
    await asyncio.sleep(0.3)

    # Should be acquirable now that it's expired
    async with lock.acquire(key, ttl_seconds=30):
        val = await fake_redis.get(key)
        assert val is not None


@pytest.mark.asyncio
async def test_lock_only_released_by_owner(fake_redis):
    lock = RedisLock(redis=fake_redis)
    key = f"execution:{uuid.uuid4()}:lock"

    # Simulate another owner holding the lock
    await fake_redis.set(key, "other-owner-token", ex=30)

    # Our lock should fail to acquire
    with pytest.raises(LockAcquisitionError):
        async with lock.acquire(key, ttl_seconds=30):
            pass

    # The other owner's lock must still be present (we didn't delete it)
    val = await fake_redis.get(key)
    assert val is not None


@pytest.mark.asyncio
async def test_lock_released_on_exception(fake_redis):
    lock = RedisLock(redis=fake_redis)
    key = f"execution:{uuid.uuid4()}:lock"

    with pytest.raises(ValueError):
        async with lock.acquire(key, ttl_seconds=30):
            raise ValueError("something went wrong")

    # Lock must be released even though an exception was raised
    val = await fake_redis.get(key)
    assert val is None


@pytest.mark.asyncio
async def test_heartbeat_renews_ttl(fake_redis):
    lock = RedisLock(redis=fake_redis)
    key = f"execution:{uuid.uuid4()}:lock"

    # Acquire with 2s TTL (heartbeat fires at 1s)
    async with lock.acquire(key, ttl_seconds=2):
        # Immediately after acquire, TTL should be ~2s
        ttl_before = await fake_redis.ttl(key)
        assert ttl_before > 0

        # Wait for heartbeat to fire (interval = ttl/2 = 1s)
        await asyncio.sleep(1.1)

        # TTL should have been renewed (reset back toward 2s)
        ttl_after = await fake_redis.ttl(key)
        assert ttl_after > 0  # still alive and renewed
