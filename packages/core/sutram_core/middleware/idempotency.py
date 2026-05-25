# packages/core/sutram_core/middleware/idempotency.py
from __future__ import annotations

import redis.asyncio as aioredis


class IdempotencyStore:
    """Deduplicates requests by Idempotency-Key using Redis SET NX.

    Keys are namespaced under 'idempotency:' to avoid collisions with
    other Redis keys (locks, rate limits, streams).
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def check_and_store(self, key: str, ttl_seconds: int = 86400) -> bool:
        """Check if key has been seen before and store it if not.

        Returns True if this is a duplicate request (key already exists).
        Returns False if this is the first time this key is seen.
        """
        redis_key = f"idempotency:{key}"
        stored = await self._redis.set(redis_key, "1", nx=True, ex=ttl_seconds)
        # SET NX returns truthy (True) if key was newly set, falsy (None/False) if already existed
        return not stored

    async def delete(self, key: str) -> None:
        """Delete the idempotency key so the client can retry after a failure."""
        redis_key = f"idempotency:{key}"
        await self._redis.delete(redis_key)
