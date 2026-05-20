# tests/conftest.py
import fakeredis
import fakeredis.aioredis
import pytest


@pytest.fixture
async def fake_redis():
    server = fakeredis.FakeServer()
    client = fakeredis.aioredis.FakeRedis(server=server)
    yield client
    await client.aclose()


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Prevent lru_cache on get_settings from bleeding between tests."""
    yield
    from app.settings import get_settings

    get_settings.cache_clear()
    # Also clear CoreSettings cache
    try:
        from sutram_core.settings import get_settings as core_get_settings

        core_get_settings.cache_clear()
    except Exception:
        pass
