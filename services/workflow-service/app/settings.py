from __future__ import annotations

from functools import lru_cache

from sutram_core.settings import CoreSettings


class WorkflowServiceSettings(CoreSettings):  # type: ignore[misc]
    # inherits model_config from CoreSettings — no need to redeclare

    # Separate Redis logical DBs (avoids cross-concern key collisions)
    redis_streams_url: str = "redis://localhost:6379/1"
    redis_locks_url: str = "redis://localhost:6379/2"
    redis_cache_url: str = "redis://localhost:6379/0"

    # Celery — dedicated DBs to avoid key collisions with cache (DB 0)
    celery_broker_url: str = "redis://localhost:6379/3"
    celery_result_backend: str = "redis://localhost:6379/4"

    # Memory service
    memory_service_url: str = "http://memory-service:8002"

    # Webhook secret encryption (AES-GCM). Must be 32 bytes hex-encoded (64 chars).
    webhook_secret_encryption_key: str = "0" * 64  # dev placeholder — override in production

    # Execution limits
    max_concurrent_executions_global: int = 1000
    execution_heartbeat_interval_seconds: int = 15
    execution_stale_threshold_minutes: int = 5


@lru_cache
def get_settings() -> WorkflowServiceSettings:
    return WorkflowServiceSettings()
