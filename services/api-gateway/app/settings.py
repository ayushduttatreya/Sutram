from __future__ import annotations

from functools import lru_cache

from sutram_core.settings import CoreSettings


class APIGatewaySettings(CoreSettings):  # type: ignore[misc]
    # Downstream service URLs
    workflow_service_url: str = "http://workflow-service:8001"
    memory_service_url: str = "http://memory-service:8002"
    observability_service_url: str = "http://observability-service:8003"

    # Redis for rate limiting — DB 3 per infra/redis.conf spec
    redis_rate_limit_url: str = "redis://localhost:6379/3"

    # Redis for idempotency dedup — DB 0 (general cache)
    redis_idempotency_url: str = "redis://localhost:6379/0"

    # Per-tenant rate limit
    requests_per_minute: int = 1000

    # Proxy timeouts
    proxy_timeout_seconds: float = 30.0
    # None = no timeout for SSE streams (long-lived connections)
    stream_timeout_seconds: float | None = None


@lru_cache
def get_settings() -> APIGatewaySettings:
    return APIGatewaySettings()
