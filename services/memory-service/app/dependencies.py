from __future__ import annotations
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sutram_core.db.session import create_engine, create_session_factory
from sutram_core.embedding.openai import OpenAIEmbedder
from sutram_core.embedding.registry import EmbeddingRegistry
from sutram_core.streams.redis_streams import StreamProducer

from app.retrieval.embedder import Embedder
from app.retrieval.searcher import Searcher
from app.settings import get_settings

_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis_streams: aioredis.Redis | None = None
_redis_cache: aioredis.Redis | None = None
_registry: EmbeddingRegistry | None = None
_openai_embedder: OpenAIEmbedder | None = None
_embedder: Embedder | None = None


def init_db() -> None:
    global _session_factory
    settings = get_settings()
    engine = create_engine(settings.database_url, use_nullpool=True)
    _session_factory = create_session_factory(engine)


def init_redis() -> None:
    global _redis_streams, _redis_cache
    settings = get_settings()
    _redis_streams = aioredis.from_url(settings.redis_streams_url)
    _redis_cache = aioredis.from_url(settings.redis_cache_url)


def init_embedding() -> None:
    global _registry, _openai_embedder, _embedder
    if _redis_cache is None:
        raise RuntimeError("Redis must be initialized before embedding")
    settings = get_settings()
    _registry = EmbeddingRegistry()
    _openai_embedder = OpenAIEmbedder(api_key=settings.openai_api_key)
    _registry.register(_openai_embedder)
    _embedder = Embedder(
        registry=_registry,
        redis=_redis_cache,
        cache_ttl_seconds=settings.embedding_cache_ttl_seconds,
    )


async def close_redis() -> None:
    global _redis_streams, _redis_cache
    if _redis_streams is not None:
        await _redis_streams.aclose()
        _redis_streams = None
    if _redis_cache is not None:
        await _redis_cache.aclose()
        _redis_cache = None


async def close_embedding() -> None:
    global _openai_embedder
    if _openai_embedder is not None:
        await _openai_embedder.aclose()
        _openai_embedder = None


def get_embedder() -> Embedder:
    if _embedder is None:
        raise RuntimeError("Embedding not initialized — call init_embedding() at startup")
    return _embedder


def get_searcher() -> Searcher:
    settings = get_settings()
    return Searcher(
        embedder=get_embedder(),
        candidate_limit=settings.ann_candidate_limit,
        half_life_days=settings.recency_half_life_days,
    )


def get_stream_producer() -> StreamProducer:
    if _redis_streams is None:
        raise RuntimeError("Redis not initialized — call init_redis() at startup")
    return StreamProducer(redis=_redis_streams)


def get_redis_cache() -> aioredis.Redis:
    if _redis_cache is None:
        raise RuntimeError("Redis not initialized — call init_redis() at startup")
    return _redis_cache


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
