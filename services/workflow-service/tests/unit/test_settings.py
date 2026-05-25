from app.settings import WorkflowServiceSettings


def test_default_redis_streams_url():
    s = WorkflowServiceSettings()
    assert s.redis_streams_url == "redis://localhost:6379/1"


def test_default_redis_locks_url():
    s = WorkflowServiceSettings()
    assert s.redis_locks_url == "redis://localhost:6379/2"


def test_inherits_from_core_settings():
    from sutram_core.settings import CoreSettings

    assert issubclass(WorkflowServiceSettings, CoreSettings)


def test_webhook_key_default_is_64_chars():
    s = WorkflowServiceSettings()
    assert len(s.webhook_secret_encryption_key) == 64


def test_celery_uses_dedicated_redis_dbs():
    s = WorkflowServiceSettings()
    assert s.celery_broker_url == "redis://localhost:6379/3"
    assert s.celery_result_backend == "redis://localhost:6379/4"
    # Must not use the same DB as cache (DB 0) or streams (DB 1) or locks (DB 2)
    assert "/0" not in s.celery_broker_url
    assert "/0" not in s.celery_result_backend


def test_production_env_rejects_zero_encryption_key():
    import pytest
    from pydantic import ValidationError

    with pytest.raises((ValidationError, ValueError)):
        WorkflowServiceSettings(
            sutram_env="production",
            webhook_secret_encryption_key="0" * 64,
        )


def test_production_env_rejects_default_jwt_secret():
    import pytest
    from pydantic import ValidationError

    with pytest.raises((ValidationError, ValueError)):
        WorkflowServiceSettings(
            sutram_env="production",
            jwt_secret="dev-secret-change-in-production",
            webhook_secret_encryption_key="a" * 64,
            internal_auth_token="real-token",
        )


def test_development_env_allows_default_secrets():
    s = WorkflowServiceSettings(sutram_env="development")
    assert s.webhook_secret_encryption_key == "0" * 64


def test_production_env_accepts_valid_secrets():
    import secrets

    s = WorkflowServiceSettings(
        sutram_env="production",
        webhook_secret_encryption_key=secrets.token_hex(32),
        jwt_secret="a-real-jwt-secret-that-is-not-the-default",
        internal_auth_token="a-real-internal-token",
    )
    assert s.sutram_env == "production"
