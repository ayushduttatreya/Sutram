"""ANN searcher with ADR-008 and ADR-007 compliance.

ADR-008: WHERE tenant_id = :tid appears BEFORE ORDER BY embedding <=> :vec.
         The ivfflat index only scans the pre-filtered tenant's vectors.

ADR-007: During model migrations, multiple embedding_model values may coexist.
         We discover distinct models per tenant and run one ANN query per model.
         Only same-model vectors are compared (AND embedding_model = :model).
         Results from all models are merged before reranking.
"""
from __future__ import annotations
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.embedder import Embedder
from app.retrieval.reranker import CandidateRow, rerank


class Searcher:
    def __init__(
        self,
        embedder: Embedder,
        candidate_limit: int = 50,
        half_life_days: float = 30.0,
    ) -> None:
        self._embedder = embedder
        self._candidate_limit = candidate_limit
        self._half_life_days = half_life_days

    async def search(
        self,
        query: str,
        tenant_id: uuid.UUID,
        top_k: int,
        session: AsyncSession,
        memory_types: list[str] | None = None,
    ) -> list[CandidateRow]:
        """Run ADR-008 compliant ANN search across all embedding models for this tenant."""
        # Discover distinct embedding models present for this tenant (ADR-007)
        models_result = await session.execute(
            text(
                "SELECT DISTINCT embedding_model FROM memory_items "
                "WHERE tenant_id = :tid AND compressed = false"
            ),
            {"tid": tenant_id},
        )
        models = [row[0] for row in models_result]
        if not models:
            return []

        type_filter = memory_types or ["episodic", "semantic", "procedural"]
        all_candidates: list[CandidateRow] = []

        for model_name in models:
            # Embed query using the same model as the candidate rows (ADR-007)
            vector = await self._embedder.embed(query, model=model_name)
            vec_str = "[" + ",".join(str(v) for v in vector) + "]"

            # ADR-008: WHERE tenant_id = :tid BEFORE ORDER BY embedding <=> :vec
            # ADR-007: AND embedding_model = :model — only same-model comparisons
            rows = await session.execute(
                text("""
                    WITH q AS (SELECT :vec::vector AS qvec)
                    SELECT
                        id::text,
                        content,
                        metadata,
                        embedding_model,
                        accessed_at,
                        access_count,
                        1 - (embedding <=> q.qvec) AS similarity
                    FROM memory_items, q
                    WHERE tenant_id = :tid
                      AND compressed = false
                      AND memory_type = ANY(:types)
                      AND embedding_model = :model
                    ORDER BY embedding <=> q.qvec
                    LIMIT :lim
                """),
                {
                    "vec": vec_str,
                    "tid": tenant_id,
                    "types": type_filter,
                    "model": model_name,
                    "lim": self._candidate_limit,
                },
            )

            for row in rows:
                all_candidates.append(
                    CandidateRow(
                        id=row[0],          # already str from id::text cast
                        content=row[1],
                        metadata=row[2] or {},
                        embedding_model=row[3],
                        accessed_at=row[4],
                        access_count=row[5],
                        similarity=float(row[6]),
                    )
                )

        return rerank(all_candidates, top_k=top_k, half_life_days=self._half_life_days)
