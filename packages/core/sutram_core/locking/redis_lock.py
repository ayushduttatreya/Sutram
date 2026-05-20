from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

import redis.asyncio as aioredis

# Lua script: atomically release lock only if we own it
_RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


class LockAcquisitionError(Exception):
    """Raised when a distributed lock cannot be acquired because it is already held."""


class RedisLock:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    @asynccontextmanager
    async def acquire(
        self,
        key: str,
        ttl_seconds: int = 30,
    ) -> AsyncGenerator[str, None]:
        """Acquire a Redis lock using SET NX EX.

        Raises LockAcquisitionError if the lock is already held.
        Starts a heartbeat task that renews the TTL every ttl/2 seconds.
        Releases the lock atomically on exit (only if we still own it).

        block_ms: milliseconds to block waiting for messages.
                  None = non-blocking (returns immediately if no messages).

        Yields the lock token (a UUID string).
        """
        token = str(uuid.uuid4())
        acquired = await self._redis.set(key, token, nx=True, ex=ttl_seconds)
        if not acquired:
            raise LockAcquisitionError(f"Could not acquire lock: {key}")

        heartbeat_task = asyncio.create_task(self._renew_heartbeat(key, token, ttl_seconds))
        try:
            yield token
        finally:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
            # Atomically check ownership and delete in one round-trip
            await self._redis.eval(_RELEASE_SCRIPT, 1, key, token)  # type: ignore[misc]

    async def _renew_heartbeat(self, key: str, token: str, ttl_seconds: int) -> None:
        """Renew lock TTL every ttl/2 seconds while held."""
        interval = max(ttl_seconds / 2, 1)
        while True:
            await asyncio.sleep(interval)
            current = await self._redis.get(key)
            if current is None:
                break
            current_str = current.decode() if isinstance(current, bytes) else current
            if current_str == token:
                await self._redis.expire(key, ttl_seconds)
            else:
                break
