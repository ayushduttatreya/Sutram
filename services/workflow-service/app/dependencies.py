# app/dependencies.py
from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sutram_core.db.session import create_engine, create_session_factory
from sutram_core.locking.redis_lock import RedisLock
from sutram_core.middleware.tenant import set_tenant_context
from sutram_core.streams.redis_streams import StreamProducer

from app.settings import get_settings

_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis_streams: aioredis.Redis | None = None
_redis_locks: aioredis.Redis | None = None


def init_db() -> None:
    global _session_factory
    settings = get_settings()
    engine = create_engine(settings.database_url, use_nullpool=True)
    _session_factory = create_session_factory(engine)


def init_redis() -> None:
    global _redis_streams, _redis_locks
    settings = get_settings()
    _redis_streams = aioredis.from_url(settings.redis_streams_url)  # type: ignore[no-untyped-call]
    _redis_locks = aioredis.from_url(settings.redis_locks_url)  # type: ignore[no-untyped-call]


async def close_redis() -> None:
    """Close Redis connections on shutdown."""
    global _redis_streams, _redis_locks
    if _redis_streams is not None:
        await _redis_streams.aclose()
        _redis_streams = None
    if _redis_locks is not None:
        await _redis_locks.aclose()
        _redis_locks = None


def get_redis_lock() -> RedisLock:
    if _redis_locks is None:
        raise RuntimeError("Redis not initialised — call init_redis() at startup")
    return RedisLock(redis=_redis_locks)


def get_stream_producers() -> tuple[StreamProducer, StreamProducer]:
    if _redis_streams is None:
        raise RuntimeError("Redis not initialised — call init_redis() at startup")
    return StreamProducer(redis=_redis_streams), StreamProducer(redis=_redis_streams)


@asynccontextmanager
async def get_db_session_context() -> AsyncIterator[AsyncSession]:
    """Async context manager for non-FastAPI use (Celery tasks, recovery handler)."""
    if _session_factory is None:
        raise RuntimeError("DB not initialised — call init_db() at startup")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a DB session with commit/rollback."""
    async with get_db_session_context() as session:
        yield session


async def get_tenant_session(
    tenant_id: str,
) -> AsyncGenerator[AsyncSession, None]:
    """Yields a DB session with RLS context set for the given tenant."""
    async for session in get_db_session():
        await set_tenant_context(session, tenant_id)
        yield session
