# packages/core/sutram_core/middleware/rate_limit.py
from __future__ import annotations

import time

import redis.asyncio as aioredis

# Lua script: atomically increment counter and set TTL on first request.
# Prevents immortal keys if process crashes between INCR and EXPIRE.
_INCR_WITH_TTL_SCRIPT = """
local count = redis.call("INCR", KEYS[1])
if count == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
return count
"""


class RateLimitExceeded(Exception):
    def __init__(self, tenant_id: str, limit: int) -> None:
        super().__init__(f"Rate limit of {limit} req/min exceeded for tenant {tenant_id}")
        self.tenant_id = tenant_id
        self.limit = limit


class RateLimiter:
    """Fixed-window rate limiter backed by Redis.

    Uses 1-minute windows keyed by tenant_id. Each tenant gets an independent
    counter. Counter and TTL are set atomically via Lua script.

    Known trade-offs (acceptable for MVP):
    - Fixed-window burst: a tenant can send 2x the limit across a window
      boundary (last second of window N + first second of window N+1).
    - Clock drift: in multi-pod deployments, pods with diverging system clocks
      can land in different windows, potentially exceeding the intended limit.
    """

    _WINDOW_SECONDS = 60
    _TTL_SECONDS = 120  # 2 windows — ensures key expires even if window rolls over

    def __init__(self, redis: aioredis.Redis, requests_per_minute: int = 1000) -> None:
        self._redis = redis
        self._requests_per_minute = requests_per_minute

    async def check(self, tenant_id: str) -> None:
        """Increment request counter. Raises RateLimitExceeded if over limit."""
        window = int(time.time()) // self._WINDOW_SECONDS
        key = f"rate:{tenant_id}:{window}"

        count = await self._redis.eval(_INCR_WITH_TTL_SCRIPT, 1, key, self._TTL_SECONDS)  # type: ignore[misc]

        if count > self._requests_per_minute:
            raise RateLimitExceeded(tenant_id, self._requests_per_minute)
