from app.settings import ObservabilityServiceSettings


def test_redis_streams_url_is_db1():
    s = ObservabilityServiceSettings()
    assert "/1" in s.redis_streams_url


def test_redis_buffer_url_is_db0():
    s = ObservabilityServiceSettings()
    assert "/0" in s.redis_buffer_url


def test_consumer_group_default():
    s = ObservabilityServiceSettings()
    assert s.consumer_group == "observability-workers"


def test_trace_buffer_ttl_is_600_seconds():
    s = ObservabilityServiceSettings()
    assert s.trace_buffer_ttl_seconds == 600


def test_slow_threshold_is_30_seconds():
    s = ObservabilityServiceSettings()
    assert s.slow_execution_threshold_ms == 30_000


def test_fast_sample_rate_is_10_percent():
    s = ObservabilityServiceSettings()
    assert s.fast_execution_sample_rate == 0.10


def test_inherits_from_core_settings():
    from sutram_core.settings import CoreSettings

    assert issubclass(ObservabilityServiceSettings, CoreSettings)
