"""Tail-based trace sampler using a Redis Hash buffer per execution.

Key design: Redis Hash (not List) at key trace:buffer:{execution_id}.
Hash field = span_key (e.g. "step:0", "started:{id}").
HSET is idempotent: redelivered spans overwrite, preventing duplicates.

Decision on ExecutionCompletedEvent:
- Any failure flag → keep 100%
- total_duration_ms > slow_threshold_ms → keep 100%
- Otherwise → keep at sample_rate probability (default 10%)
"""

from __future__ import annotations

import json
import random
import uuid
from typing import Any

import redis.asyncio as aioredis


class TailSampler:
    def __init__(
        self,
        redis: aioredis.Redis,
        ttl_seconds: int = 600,
        sample_rate: float = 0.10,
        slow_threshold_ms: int = 30_000,
    ) -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        self._sample_rate = sample_rate
        self._slow_threshold_ms = slow_threshold_ms

    def _buffer_key(self, execution_id: uuid.UUID) -> str:
        return f"trace:buffer:{execution_id}"

    def _failure_key(self, execution_id: uuid.UUID) -> str:
        return f"trace:has_failure:{execution_id}"

    async def buffer_span(
        self,
        execution_id: uuid.UUID,
        span_key: str,
        span_data: dict[str, Any],
    ) -> None:
        """Store span in Hash buffer. Same span_key overwrites (idempotent on redelivery)."""
        key = self._buffer_key(execution_id)
        await self._redis.hset(key, span_key, json.dumps(span_data))  # type: ignore[misc]
        await self._redis.expire(key, self._ttl)

    async def mark_has_failure(self, execution_id: uuid.UUID) -> None:
        """Flag this execution as having a failed step — causes 100% keep."""
        key = self._failure_key(execution_id)
        await self._redis.set(key, "1", ex=self._ttl)

    async def should_keep(self, execution_id: uuid.UUID, total_duration_ms: int) -> bool:
        """Decide whether to flush this trace to the database."""
        has_failure = await self._redis.get(self._failure_key(execution_id))
        if has_failure:
            return True
        if total_duration_ms > self._slow_threshold_ms:
            return True
        return random.random() < self._sample_rate

    async def flush(self, execution_id: uuid.UUID) -> list[dict[str, Any]]:
        """Read all buffered spans, delete buffer + failure flag, return spans."""
        key = self._buffer_key(execution_id)
        raw = await self._redis.hgetall(key)  # type: ignore[misc]
        spans = [json.loads(v) for v in raw.values()]
        await self._redis.delete(key, self._failure_key(execution_id))
        return spans
