from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sutram_core.events.memory import MemorySearchedEvent, MemoryWrittenEvent
from sutram_core.middleware.internal_auth import InternalAuthError, verify_internal_token
from sutram_core.middleware.tenant import set_tenant_context
from sutram_core.streams.redis_streams import StreamProducer

from app.dependencies import (
    get_db_session,
    get_embedder,
    get_redis_cache,
    get_searcher,
    get_stream_producer,
)
from app.models.orm import MemoryItemORM
from app.retrieval.embedder import Embedder
from app.retrieval.searcher import Searcher
from app.schemas.memory import (
    MemoryItemCreate,
    MemoryItemResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemorySearchResult,
)
from app.settings import get_settings

router = APIRouter(tags=["memory"])

DBSession = Annotated[AsyncSession, Depends(get_db_session)]
RedisCache = Annotated[aioredis.Redis, Depends(get_redis_cache)]
StreamProd = Annotated[StreamProducer, Depends(get_stream_producer)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
SearcherDep = Annotated[Searcher, Depends(get_searcher)]


async def _get_tenant_id(
    x_internal_token: str = Header(..., alias="X-Internal-Token"),  # noqa: B008
    x_tenant_id: uuid.UUID = Header(..., alias="X-Tenant-ID"),  # noqa: B008
) -> uuid.UUID:
    """Verify X-Internal-Token and extract tenant_id from header."""
    settings = get_settings()
    try:
        verify_internal_token(x_internal_token, settings.internal_auth_token)
    except InternalAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return x_tenant_id


TenantID = Annotated[uuid.UUID, Depends(_get_tenant_id)]


async def _invalidate_query_cache(redis: aioredis.Redis, tenant_id: uuid.UUID) -> None:
    """Scan and delete all hot query cache entries for this tenant."""
    pattern = f"memory:query:{tenant_id}:*"
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break


async def _update_access_stats_bg(
    item_ids: list[uuid.UUID],
    tenant_id: uuid.UUID,
) -> None:
    """Background task: update access stats with a fresh DB session."""
    from app.dependencies import get_db_session_context

    try:
        async with get_db_session_context() as fresh_session:
            await fresh_session.execute(
                text(
                    "UPDATE memory_items SET accessed_at = NOW(), access_count = access_count + 1 "
                    "WHERE id = ANY(:ids) AND tenant_id = :tid"
                ),
                {"ids": item_ids, "tid": tenant_id},
            )
    except Exception:
        pass


@router.post("/memory/items", response_model=MemoryItemResponse, status_code=201)
async def store_memory(
    body: MemoryItemCreate,
    session: DBSession,
    tenant_id: TenantID,
    embedder: EmbedderDep,
    producer: StreamProd,
    redis: RedisCache,
) -> MemoryItemORM:
    settings = get_settings()

    await set_tenant_context(session, str(tenant_id))
    vector = await embedder.embed(body.content, model=settings.default_embedding_model)

    item_id = uuid.uuid4()
    orm = MemoryItemORM(
        id=item_id,
        tenant_id=tenant_id,
        memory_type=body.memory_type.value,
        content=body.content,
        embedding=vector,
        embedding_model=settings.default_embedding_model,
        extra_metadata=body.extra_metadata,
        retention_policy=body.retention_policy,
    )
    session.add(orm)
    await session.flush()
    await _invalidate_query_cache(redis, tenant_id)
    await producer.publish(
        "memory.events",
        MemoryWrittenEvent(
            tenant_id=tenant_id, memory_item_id=item_id, memory_type=body.memory_type.value
        ),
    )
    return orm


@router.get("/memory/items/{item_id}", response_model=MemoryItemResponse)
async def get_memory_item(
    item_id: uuid.UUID,
    session: DBSession,
    tenant_id: TenantID,
) -> MemoryItemORM:
    await set_tenant_context(session, str(tenant_id))
    result = await session.execute(
        select(MemoryItemORM).where(
            MemoryItemORM.id == item_id, MemoryItemORM.tenant_id == tenant_id
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Memory item not found")
    return item


@router.delete("/memory/items/{item_id}", status_code=204)
async def forget_memory(
    item_id: uuid.UUID,
    session: DBSession,
    tenant_id: TenantID,
    redis: RedisCache,
) -> None:
    await set_tenant_context(session, str(tenant_id))
    result = await session.execute(
        select(MemoryItemORM).where(
            MemoryItemORM.id == item_id, MemoryItemORM.tenant_id == tenant_id
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Memory item not found")
    await session.delete(item)
    await session.flush()
    await _invalidate_query_cache(redis, tenant_id)


@router.post("/memory/search", response_model=MemorySearchResponse)
async def search_memory(
    body: MemorySearchRequest,
    session: DBSession,
    tenant_id: TenantID,
    background_tasks: BackgroundTasks,
    redis: RedisCache,
    searcher: SearcherDep,
    producer: StreamProd,
) -> MemorySearchResponse:
    settings = get_settings()
    start_ms = int(time.time() * 1000)

    type_strs = sorted([t.value for t in body.memory_types]) if body.memory_types else ["all"]
    _raw = (body.query + "|" + ",".join(type_strs)).encode()
    cache_key = f"memory:query:{tenant_id}:{hashlib.sha256(_raw).hexdigest()}"

    cached = await redis.get(cache_key)
    if cached is not None:
        latency_ms = int(time.time() * 1000) - start_ms
        cached_results = json.loads(cached)
        await producer.publish(
            "memory.events",
            MemorySearchedEvent(
                tenant_id=tenant_id,
                query_hash=hashlib.sha256(body.query.encode()).hexdigest(),
                results_count=len(cached_results),
                latency_ms=latency_ms,
                cache_hit=True,
            ),
        )
        return MemorySearchResponse(results=cached_results, cache_hit=True, latency_ms=latency_ms)

    await set_tenant_context(session, str(tenant_id))
    memory_types = [t.value for t in body.memory_types] if body.memory_types else None
    candidates = await searcher.search(
        query=body.query,
        tenant_id=tenant_id,
        top_k=body.top_k,
        session=session,
        memory_types=memory_types,
    )

    results: list[MemorySearchResult] = []
    if candidates:
        candidate_ids = [uuid.UUID(c.candidate.id) for c in candidates]
        rows_result = await session.execute(
            select(MemoryItemORM).where(MemoryItemORM.id.in_(candidate_ids))
        )
        rows_by_id = {str(row.id): row for row in rows_result.scalars()}
        for scored_cand in candidates:
            orm_row = rows_by_id.get(scored_cand.candidate.id)
            if orm_row:
                results.append(
                    MemorySearchResult(
                        item=MemoryItemResponse.model_validate(orm_row),
                        score=round(scored_cand.score, 4),
                        similarity=scored_cand.candidate.similarity,
                    )
                )
        background_tasks.add_task(_update_access_stats_bg, candidate_ids, tenant_id)

    latency_ms = int(time.time() * 1000) - start_ms
    await redis.setex(
        cache_key,
        settings.query_cache_ttl_seconds,
        json.dumps([r.model_dump(mode="json") for r in results]),
    )
    await producer.publish(
        "memory.events",
        MemorySearchedEvent(
            tenant_id=tenant_id,
            query_hash=hashlib.sha256(body.query.encode()).hexdigest(),
            results_count=len(results),
            latency_ms=latency_ms,
            cache_hit=False,
        ),
    )
    return MemorySearchResponse(results=results, cache_hit=False, latency_ms=latency_ms)
