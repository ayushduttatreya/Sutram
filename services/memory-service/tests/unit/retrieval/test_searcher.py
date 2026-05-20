import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from app.retrieval.searcher import Searcher
from app.retrieval.reranker import CandidateRow, ScoredCandidate
from app.retrieval.embedder import Embedder


def make_mock_embedder() -> Embedder:
    embedder = MagicMock(spec=Embedder)
    embedder.embed = AsyncMock(return_value=[0.1] * 1536)
    return embedder


@pytest.mark.asyncio
async def test_search_returns_empty_when_no_models_for_tenant():
    """If no items exist for tenant, distinct model query returns empty -> empty results."""
    session = AsyncMock()
    # First execute: distinct models query returns nothing
    empty_result = MagicMock()
    empty_result.__iter__ = MagicMock(return_value=iter([]))
    session.execute = AsyncMock(return_value=empty_result)

    embedder = make_mock_embedder()
    searcher = Searcher(embedder=embedder, candidate_limit=50, half_life_days=30.0)

    results = await searcher.search(
        query="test query",
        tenant_id=uuid.uuid4(),
        top_k=5,
        session=session,
        memory_types=["semantic"],
    )
    assert results == []
    # embedder should NOT be called if there are no models to search
    embedder.embed.assert_not_called()


@pytest.mark.asyncio
async def test_search_calls_embedder_once_per_distinct_model():
    """For each distinct embedding_model in the DB, embed the query once."""
    session = AsyncMock()

    # First execute: 2 distinct models
    model_result = MagicMock()
    model_result.__iter__ = MagicMock(
        return_value=iter([("text-embedding-3-small",), ("text-embedding-ada-002",)])
    )
    # Subsequent executes: empty candidates for each ANN query
    empty_result = MagicMock()
    empty_result.__iter__ = MagicMock(return_value=iter([]))
    session.execute = AsyncMock(side_effect=[model_result, empty_result, empty_result])

    embedder = MagicMock(spec=Embedder)
    embedder.embed = AsyncMock(return_value=[0.1] * 1536)

    searcher = Searcher(embedder=embedder, candidate_limit=50, half_life_days=30.0)
    await searcher.search(
        query="test",
        tenant_id=uuid.uuid4(),
        top_k=5,
        session=session,
        memory_types=["semantic"],
    )

    # embed called twice — once per model
    assert embedder.embed.call_count == 2
    # Verify embed was called with the correct model names
    call_models = [call.kwargs.get("model") or call.args[1] for call in embedder.embed.call_args_list]
    assert "text-embedding-3-small" in call_models
    assert "text-embedding-ada-002" in call_models


@pytest.mark.asyncio
async def test_search_passes_memory_types_filter():
    """memory_types parameter is passed to the SQL query."""
    session = AsyncMock()
    model_result = MagicMock()
    model_result.__iter__ = MagicMock(return_value=iter([("text-embedding-3-small",)]))
    empty_result = MagicMock()
    empty_result.__iter__ = MagicMock(return_value=iter([]))
    session.execute = AsyncMock(side_effect=[model_result, empty_result])

    searcher = Searcher(embedder=make_mock_embedder(), candidate_limit=50, half_life_days=30.0)
    await searcher.search(
        query="test",
        tenant_id=uuid.uuid4(),
        top_k=5,
        session=session,
        memory_types=["episodic"],
    )

    # Second execute is the ANN query — check params include memory types
    ann_call = session.execute.call_args_list[1]
    params = ann_call.args[1] if len(ann_call.args) > 1 else ann_call.kwargs.get("params", {})
    assert "types" in params
    assert "episodic" in params["types"]


@pytest.mark.asyncio
async def test_search_defaults_to_all_memory_types_when_none():
    """Omitting memory_types should search all three types."""
    session = AsyncMock()
    model_result = MagicMock()
    model_result.__iter__ = MagicMock(return_value=iter([("text-embedding-3-small",)]))
    empty_result = MagicMock()
    empty_result.__iter__ = MagicMock(return_value=iter([]))
    session.execute = AsyncMock(side_effect=[model_result, empty_result])

    searcher = Searcher(embedder=make_mock_embedder(), candidate_limit=50, half_life_days=30.0)
    await searcher.search(
        query="test",
        tenant_id=uuid.uuid4(),
        top_k=5,
        session=session,
        memory_types=None,   # explicitly None — should default to all three types
    )

    ann_call = session.execute.call_args_list[1]
    params = ann_call.args[1] if len(ann_call.args) > 1 else {}
    assert set(params.get("types", [])) == {"episodic", "semantic", "procedural"}
