from __future__ import annotations

import socket
from functools import lru_cache

from sutram_core.settings import CoreSettings


class ObservabilityServiceSettings(CoreSettings):  # type: ignore[misc]
    # Redis — consumer on DB 1 (streams), buffer on DB 0 (tail sampler)
    redis_streams_url: str = "redis://localhost:6379/1"
    redis_buffer_url: str = "redis://localhost:6379/0"

    # Stream consumer group config
    consumer_group: str = "observability-workers"
    # Unique per replica — defaults to hostname so two pods don't clash
    consumer_name: str = f"obs-worker-{socket.gethostname()}"

    # Streams to consume
    executions_stream: str = "executions"
    memory_stream: str = "memory.events"

    # Tail sampler
    trace_buffer_ttl_seconds: int = 600  # 10 minutes
    slow_execution_threshold_ms: int = 30_000  # 30 seconds → always keep
    fast_execution_sample_rate: float = 0.10  # 10% of fast successes kept

    # Consumer loop
    consumer_poll_count: int = 100
    consumer_block_ms: int = 1000
    reclaim_min_idle_ms: int = 60_000

    # Read API
    audit_log_default_page_size: int = 100
    audit_log_max_page_size: int = 1000


@lru_cache
def get_settings() -> ObservabilityServiceSettings:
    return ObservabilityServiceSettings()
