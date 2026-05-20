# services/memory-service/app/compression/compressor.py
"""LLM-based memory compression.

Process per tenant:
1. Query items WHERE compressed=false AND created_at < threshold (batch of N)
2. Call LLM to summarize batch content
3. Embed summary text with current default model
4. Insert MemorySummaryORM with original_ids + embedding
5. Mark original items as compressed=true

NOTE: No set_tenant_context call — compression job bypasses RLS to process all tenants.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.compression.archiver import Archiver
from app.models.orm import MemoryItemORM, MemorySummaryORM
from app.retrieval.embedder import Embedder
from app.settings import get_settings


class Compressor:
    def __init__(self, session: AsyncSession, embedder: Embedder) -> None:
        self._session = session
        self._embedder = embedder

    async def compress_tenant(self, tenant_id: uuid.UUID) -> int:
        """Compress old memories for one tenant. Returns number of items compressed.

        Caller is responsible for committing the session. This method calls
        flush() to make IDs available for the S3 archive step, but does NOT commit.
        Use via get_db_session_context() which commits on clean exit.
        """
        settings = get_settings()
        threshold = datetime.now(UTC) - timedelta(days=settings.compression_threshold_days)

        result = await self._session.execute(
            select(MemoryItemORM)
            .where(
                MemoryItemORM.tenant_id == tenant_id,
                MemoryItemORM.compressed.is_(False),
                MemoryItemORM.created_at < threshold,
                MemoryItemORM.retention_policy != "forever",
            )
            .order_by(MemoryItemORM.created_at.asc())
            .limit(settings.compression_batch_size)
        )
        items = list(result.scalars().all())
        if not items:
            return 0

        combined = "\n\n---\n\n".join(f"[{item.memory_type}] {item.content}" for item in items)
        summary_text = await self._summarize(combined)

        vector = await self._embedder.embed(summary_text, model=settings.default_embedding_model)

        summary = MemorySummaryORM(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            summary=summary_text,
            original_ids=[item.id for item in items],
            embedding=vector,
            embedding_model=settings.default_embedding_model,
        )
        self._session.add(summary)

        # Archive original items to S3 before marking compressed
        archiver = Archiver()
        archive_payload = [
            {
                "id": str(item.id),
                "memory_type": item.memory_type,
                "content": item.content,
                "embedding_model": item.embedding_model,
                "metadata": item.extra_metadata,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ]
        try:
            archiver.archive_items(
                tenant_id=tenant_id,
                summary_id=summary.id,
                items=archive_payload,
            )
        except Exception as e:
            # Log but don't block compression if S3 is unavailable in dev
            import logging

            logging.getLogger(__name__).warning(
                "S3 archival failed for tenant %s: %s", tenant_id, e
            )

        item_ids = [item.id for item in items]
        await self._session.execute(
            update(MemoryItemORM).where(MemoryItemORM.id.in_(item_ids)).values(compressed=True)
        )
        await self._session.flush()
        return len(items)

    async def _summarize(self, content: str) -> str:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                settings.compression_llm_url,
                json={
                    "model": settings.compression_llm_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Summarize the following memories concisely,"
                                " preserving key facts, decisions, and patterns."
                            ),
                        },
                        {"role": "user", "content": content},
                    ],
                    "max_tokens": 500,
                },
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                timeout=30.0,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return str(data["choices"][0]["message"]["content"])
