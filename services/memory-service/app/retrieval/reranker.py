"""Composite reranker: similarity * 0.6 + recency * 0.3 + freq * 0.1

Recency: exponential decay with configurable half-life (default 30 days).
Frequency: min(log(access_count + 1), 2.0) — capped to prevent high-access items
           from overwhelming the similarity signal (0.1 weight * max 2.0 = 0.2 max contribution).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, NamedTuple


@dataclass(frozen=True)
class CandidateRow:
    id: str
    content: str
    metadata: dict[str, Any]
    embedding_model: str
    accessed_at: datetime
    access_count: int
    similarity: float
    memory_type: str = "episodic"  # default for backwards compat (summaries use episodic decay)


class ScoredCandidate(NamedTuple):
    score: float
    candidate: CandidateRow


_FREQ_CAP = 2.0  # caps log(access_count+1) so freq term max = 0.1 * 2.0 = 0.2


def recency_score(accessed_at: datetime, half_life_days: float = 30.0) -> float:
    """Exponential decay: 1.0 at access time, ~0.5 at half_life_days, decays to 0."""
    now = datetime.now(UTC)
    age_days = (now - accessed_at).total_seconds() / 86400.0
    return math.exp(-age_days * math.log(2) / half_life_days)


_TYPE_HALF_LIFE: dict[str, float] = {
    "episodic": 30.0,    # decay over time — these are event-specific
    "semantic": float("inf"),   # never decay — stable facts
    "procedural": float("inf"), # never decay — stable instructions
}


def rerank(
    candidates: list[CandidateRow],
    top_k: int,
    half_life_days: float = 30.0,  # kept for backwards compat, used as episodic default
) -> list[ScoredCandidate]:
    """Score and sort candidates by composite score. Return top_k as ScoredCandidate list."""
    scored: list[ScoredCandidate] = []
    for c in candidates:
        effective_half_life = _TYPE_HALF_LIFE.get(c.memory_type, half_life_days)
        rec = recency_score(c.accessed_at, effective_half_life)
        freq = min(math.log(c.access_count + 1), _FREQ_CAP)
        score = c.similarity * 0.6 + rec * 0.3 + freq * 0.1
        scored.append(ScoredCandidate(score=score, candidate=c))
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:top_k]
