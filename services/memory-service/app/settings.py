from __future__ import annotations
from functools import lru_cache

from sutram_core.settings import CoreSettings


class MemoryServiceSettings(CoreSettings):
    # Redis logical DBs
    redis_streams_url: str = "redis://localhost:6379/1"   # stream publishing
    redis_cache_url: str = "redis://localhost:6379/0"      # hot query + embedding cache

    # Celery (dedicated DBs — no collision with cache)
    celery_broker_url: str = "redis://localhost:6379/3"
    celery_result_backend: str = "redis://localhost:6379/4"

    # Embedding
    default_embedding_model: str = "text-embedding-3-small"
    embedding_cache_ttl_seconds: int = 3600   # 1 hour

    # Hot query cache
    query_cache_ttl_seconds: int = 300         # 5 minutes

    # ANN search
    ann_candidate_limit: int = 50              # over-fetch before rerank

    # Recency decay (exponential half-life)
    recency_half_life_days: float = 30.0

    # Compression job
    compression_threshold_days: int = 7
    compression_batch_size: int = 100
    compression_llm_url: str = "https://api.openai.com/v1/chat/completions"
    compression_llm_model: str = "gpt-4o-mini"

    # S3 archival
    s3_bucket: str = "sutram-memory-archive"
    s3_region: str = "us-east-1"
    s3_prefix: str = "memories"
    s3_endpoint_url: str | None = None   # override for local MinIO: http://localhost:9000


@lru_cache
def get_settings() -> MemoryServiceSettings:
    return MemoryServiceSettings()
