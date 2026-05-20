import pytest
import fakeredis
import fakeredis.aioredis


@pytest.fixture
async def fake_redis():
    server = fakeredis.FakeServer()
    client = fakeredis.aioredis.FakeRedis(server=server)
    yield client
    await client.aclose()
