# services/observability-service/app/dependencies.py
from __future__ import annotations
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sutram_core.db.session import create_engine, create_session_factory
from sutram_core.streams.redis_streams import StreamConsumerGroup

from app.settings import get_settings

_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis_streams: aioredis.Redis | None = None
_redis_buffer: aioredis.Redis | None = None


def init_db() -> None:
    global _session_factory
    settings = get_settings()
    engine = create_engine(settings.database_url, use_nullpool=True)
    _session_factory = create_session_factory(engine)


def init_redis() -> None:
    global _redis_streams, _redis_buffer
    settings = get_settings()
    _redis_streams = aioredis.from_url(settings.redis_streams_url)
    _redis_buffer = aioredis.from_url(settings.redis_buffer_url)


async def close_redis() -> None:
    global _redis_streams, _redis_buffer
    if _redis_streams is not None:
        await _redis_streams.aclose()
        _redis_streams = None
    if _redis_buffer is not None:
        await _redis_buffer.aclose()
        _redis_buffer = None


def get_redis_streams() -> aioredis.Redis:
    if _redis_streams is None:
        raise RuntimeError("Redis streams not initialized — call init_redis() at startup")
    return _redis_streams


def get_redis_buffer() -> aioredis.Redis:
    if _redis_buffer is None:
        raise RuntimeError("Redis buffer not initialized — call init_redis() at startup")
    return _redis_buffer


def get_consumer_group() -> StreamConsumerGroup:
    return StreamConsumerGroup(redis=get_redis_streams())


@asynccontextmanager
async def get_db_session_context() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("DB not initialized — call init_db() at startup")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_db_session_context() as session:
        yield session
