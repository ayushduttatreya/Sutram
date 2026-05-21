# services/api-gateway/app/dependencies.py
"""Singleton infrastructure clients for the API gateway.

All clients are created once at startup via lifespan() in main.py and
closed on shutdown. The gateway has NO database — these are the only
infrastructure connections it needs.
"""
from __future__ import annotations

import httpx
import redis.asyncio as aioredis

from sutram_core.middleware.idempotency import IdempotencyStore
from sutram_core.middleware.rate_limit import RateLimiter

from app.settings import get_settings

_http_client: httpx.AsyncClient | None = None
_redis_rate_limit: aioredis.Redis | None = None
_redis_idempotency: aioredis.Redis | None = None
_rate_limiter: RateLimiter | None = None
_idempotency_store: IdempotencyStore | None = None


def init_clients() -> None:
    """Initialize all singleton clients. Called once at app startup (lifespan)."""
    global _http_client, _redis_rate_limit, _redis_idempotency
    global _rate_limiter, _idempotency_store

    if _http_client is not None:
        raise RuntimeError("init_clients() called twice — call close_clients() first")

    settings = get_settings()

    _http_client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(settings.proxy_timeout_seconds),
    )
    # Use gateway's own named fields — never the inherited redis_url
    _redis_rate_limit = aioredis.from_url(settings.redis_rate_limit_url)
    _redis_idempotency = aioredis.from_url(settings.redis_idempotency_url)
    _rate_limiter = RateLimiter(
        redis=_redis_rate_limit,
        requests_per_minute=settings.requests_per_minute,
    )
    _idempotency_store = IdempotencyStore(redis=_redis_idempotency)


async def close_clients() -> None:
    """Close all singleton clients. Called at app shutdown (lifespan)."""
    global _http_client, _redis_rate_limit, _redis_idempotency
    global _rate_limiter, _idempotency_store
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
    if _redis_rate_limit is not None:
        await _redis_rate_limit.aclose()
        _redis_rate_limit = None
    if _redis_idempotency is not None:
        await _redis_idempotency.aclose()
        _redis_idempotency = None
    _rate_limiter = None
    _idempotency_store = None


def get_http_client() -> httpx.AsyncClient:
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized — call init_clients() at startup")
    return _http_client


def get_rate_limiter() -> RateLimiter:
    if _rate_limiter is None:
        raise RuntimeError("Rate limiter not initialized — call init_clients() at startup")
    return _rate_limiter


def get_idempotency_store() -> IdempotencyStore:
    if _idempotency_store is None:
        raise RuntimeError("Idempotency store not initialized — call init_clients() at startup")
    return _idempotency_store
