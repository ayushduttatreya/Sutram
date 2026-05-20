# tests/unit/test_compressor.py
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.compression.compressor import Compressor
from app.models.orm import MemoryItemORM


def make_mock_item(days_old: int = 10) -> MemoryItemORM:
    item = MagicMock(spec=MemoryItemORM)
    item.id = uuid.uuid4()
    item.memory_type = "semantic"
    item.content = "test memory content"
    item.embedding_model = "text-embedding-3-small"
    item.extra_metadata = {}
    item.created_at = datetime.now(UTC) - timedelta(days=days_old)
    item.retention_policy = "90d"
    return item


@pytest.mark.asyncio
async def test_compress_tenant_returns_zero_when_no_items():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    embedder = MagicMock()
    compressor = Compressor(session=session, embedder=embedder)

    count = await compressor.compress_tenant(uuid.uuid4())
    assert count == 0


@pytest.mark.asyncio
async def test_compress_tenant_marks_items_compressed():
    session = AsyncMock()
    items = [make_mock_item(days_old=10), make_mock_item(days_old=15)]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = items
    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[0.1] * 1536)

    with (
        patch.object(Compressor, "_summarize", return_value="test summary"),
        patch("app.compression.compressor.Archiver") as mock_archiver_cls,
    ):
        mock_archiver = MagicMock()
        mock_archiver.archive_items = MagicMock()
        mock_archiver_cls.return_value = mock_archiver

        compressor = Compressor(session=session, embedder=embedder)
        count = await compressor.compress_tenant(uuid.uuid4())

    assert count == 2
    session.add.assert_called_once()  # MemorySummaryORM was added
    session.flush.assert_called_once()
