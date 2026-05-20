import pytest
import math
from datetime import datetime, timezone, timedelta
from app.retrieval.reranker import rerank, recency_score, CandidateRow


def make_candidate(
    similarity: float,
    accessed_at: datetime | None = None,
    access_count: int = 0,
) -> CandidateRow:
    if accessed_at is None:
        accessed_at = datetime.now(timezone.utc)
    return CandidateRow(
        id="test-id",
        content="test content",
        metadata={},
        embedding_model="text-embedding-3-small",
        accessed_at=accessed_at,
        access_count=access_count,
        similarity=similarity,
    )


def test_recency_score_is_one_for_just_accessed():
    score = recency_score(datetime.now(timezone.utc), half_life_days=30.0)
    assert abs(score - 1.0) < 0.01


def test_recency_score_decays_over_time():
    old = datetime.now(timezone.utc) - timedelta(days=60)
    score = recency_score(old, half_life_days=30.0)
    assert score < 0.3  # 60 days = 2 half-lives, score ~ 0.25


def test_rerank_returns_top_k():
    candidates = [make_candidate(similarity=0.9 - i * 0.1) for i in range(10)]
    results = rerank(candidates, top_k=3, half_life_days=30.0)
    assert len(results) == 3


def test_rerank_higher_similarity_wins_when_all_else_equal():
    now = datetime.now(timezone.utc)
    low = make_candidate(similarity=0.5, accessed_at=now, access_count=0)
    high = make_candidate(similarity=0.9, accessed_at=now, access_count=0)
    results = rerank([low, high], top_k=2, half_life_days=30.0)
    assert results[0].similarity == 0.9


def test_rerank_access_count_capped_to_prevent_domination():
    """log(access_count+1) is capped at 2.0 so freq term stays bounded."""
    now = datetime.now(timezone.utc)
    high_access = make_candidate(similarity=0.5, accessed_at=now, access_count=10000)
    high_sim = make_candidate(similarity=0.95, accessed_at=now, access_count=0)
    results = rerank([high_access, high_sim], top_k=2, half_life_days=30.0)
    # High similarity should rank first despite low access_count
    assert results[0].similarity == 0.95
