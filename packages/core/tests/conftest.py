# packages/core/tests/conftest.py
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
    """Clear lru_cache on get_settings between tests to prevent pollution."""
    yield
    from sutram_core.settings import get_settings

    get_settings.cache_clear()
