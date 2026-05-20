# services/memory-service/app/tasks/compress.py
"""Daily Celery beat task: compress old memories across all tenants."""
from __future__ import annotations
import asyncio

from app.tasks.celery_app import celery_app


@celery_app.task(name="memory.compress", acks_late=True)
def compress_memories() -> None:
    asyncio.run(_compress_all())


async def _compress_all() -> None:
    import logging
    from sqlalchemy import text
    from app.dependencies import get_db_session_context, get_embedder
    from app.compression.compressor import Compressor

    logger = logging.getLogger(__name__)
    embedder = get_embedder()

    # NOTE: No set_tenant_context — this job bypasses RLS to process all tenants
    async with get_db_session_context() as session:
        from app.settings import get_settings as _gs
        from datetime import timedelta, timezone, datetime as _dt
        _settings = _gs()
        threshold = _dt.now(timezone.utc) - timedelta(days=_settings.compression_threshold_days)
        result = await session.execute(
            text(
                "SELECT DISTINCT tenant_id FROM memory_items "
                "WHERE compressed = false "
                "  AND retention_policy != 'forever' "
                "  AND created_at < :threshold"
            ),
            {"threshold": threshold},
        )
        tenant_ids = [row[0] for row in result]

    for tenant_id in tenant_ids:
        try:
            async with get_db_session_context() as session:
                compressor = Compressor(session=session, embedder=embedder)
                count = await compressor.compress_tenant(tenant_id)
                if count:
                    logger.info("Compressed %d items for tenant %s", count, tenant_id)
        except Exception as e:
            logger.error("Compression failed for tenant %s: %s", tenant_id, e, exc_info=True)
