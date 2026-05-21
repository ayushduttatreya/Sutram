from app.settings import APIGatewaySettings


def test_default_workflow_service_url():
    s = APIGatewaySettings()
    assert s.workflow_service_url == "http://workflow-service:8001"


def test_default_memory_service_url():
    s = APIGatewaySettings()
    assert s.memory_service_url == "http://memory-service:8002"


def test_default_rate_limit_redis_uses_db3():
    s = APIGatewaySettings()
    assert "/3" in s.redis_rate_limit_url


def test_default_idempotency_redis_uses_db0():
    s = APIGatewaySettings()
    assert "/0" in s.redis_idempotency_url


def test_stream_timeout_defaults_to_none():
    s = APIGatewaySettings()
    assert s.stream_timeout_seconds is None


def test_inherits_from_core_settings():
    from sutram_core.settings import CoreSettings
    assert issubclass(APIGatewaySettings, CoreSettings)


def test_proxy_timeout_defaults_to_30_seconds():
    s = APIGatewaySettings()
    assert s.proxy_timeout_seconds == 30.0
