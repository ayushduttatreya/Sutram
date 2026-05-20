from app.settings import MemoryServiceSettings


def test_default_redis_streams_url():
    s = MemoryServiceSettings()
    assert s.redis_streams_url == "redis://localhost:6379/1"


def test_default_embedding_model():
    s = MemoryServiceSettings()
    assert s.default_embedding_model == "text-embedding-3-small"


def test_celery_uses_dedicated_redis_dbs():
    s = MemoryServiceSettings()
    assert "/0" not in s.celery_broker_url
    assert "/0" not in s.celery_result_backend


def test_s3_endpoint_url_defaults_to_none():
    s = MemoryServiceSettings()
    assert s.s3_endpoint_url is None


def test_inherits_from_core_settings():
    from sutram_core.settings import CoreSettings

    assert issubclass(MemoryServiceSettings, CoreSettings)
