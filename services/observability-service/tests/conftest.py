import pytest
import fakeredis
import fakeredis.aioredis


@pytest.fixture
async def fake_redis():
    server = fakeredis.FakeServer()
    client = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture(autouse=True)
def clear_settings_cache():
    yield
    from app.settings import get_settings
    get_settings.cache_clear()
    try:
        from sutram_core.settings import get_settings as core_get
        core_get.cache_clear()
    except Exception:
        pass
