"""Composite reranker: similarity * 0.6 + recency * 0.3 + freq * 0.1

Recency: exponential decay with configurable half-life (default 30 days).
Frequency: min(log(access_count + 1), 2.0) — capped to prevent high-access items
           from overwhelming the similarity signal (0.1 weight * max 2.0 = 0.2 max contribution).
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class CandidateRow:
    id: str
    content: str
    metadata: dict[str, Any]
    embedding_model: str
    accessed_at: datetime
    access_count: int
    similarity: float


_FREQ_CAP = 2.0   # caps log(access_count+1) so freq term max = 0.1 * 2.0 = 0.2


def recency_score(accessed_at: datetime, half_life_days: float = 30.0) -> float:
    """Exponential decay: 1.0 at access time, ~0.5 at half_life_days, decays to 0."""
    now = datetime.now(timezone.utc)
    age_days = (now - accessed_at).total_seconds() / 86400.0
    return math.exp(-age_days * math.log(2) / half_life_days)


def rerank(
    candidates: list[CandidateRow],
    top_k: int,
    half_life_days: float = 30.0,
) -> list[CandidateRow]:
    """Score and sort candidates by composite score. Return top_k."""
    scored: list[tuple[float, CandidateRow]] = []
    for c in candidates:
        rec = recency_score(c.accessed_at, half_life_days)
        freq = min(math.log(c.access_count + 1), _FREQ_CAP)
        score = c.similarity * 0.6 + rec * 0.3 + freq * 0.1
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]
