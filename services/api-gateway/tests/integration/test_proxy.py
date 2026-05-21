"""Integration tests for the reverse proxy using respx to mock downstream services."""

import time
import uuid
from unittest.mock import patch

import app.dependencies as deps
import fakeredis
import fakeredis.aioredis
import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from jose import jwt
from sutram_core.middleware.idempotency import IdempotencyStore
from sutram_core.middleware.rate_limit import RateLimiter


def make_jwt(tenant_id: str, secret: str = "gw-test-secret") -> str:
    return jwt.encode(
        {"tenant_id": tenant_id, "sub": tenant_id, "exp": int(time.time()) + 3600},
        secret,
        algorithm="HS256",
    )


def auth_headers(tenant_id: str) -> dict:
    return {"Authorization": f"Bearer {make_jwt(tenant_id)}"}


@pytest.fixture
def gw_client():
    """TestClient with mocked Redis and real httpx client (mocked via respx)."""
    server = fakeredis.FakeServer()
    rate_redis = fakeredis.aioredis.FakeRedis(server=server)
    idem_redis = fakeredis.aioredis.FakeRedis(server=server)

    from importlib import reload

    import app.main as m

    with patch("app.middleware.auth.get_settings") as mock_auth_settings:
        mock_auth_settings.return_value.jwt_secret = "gw-test-secret"
        mock_auth_settings.return_value.jwt_algorithm = "HS256"

        reload(m)
        application = m.create_app()

        # Wire real fake infrastructure before the lifespan fires.
        # We also patch init_clients/close_clients after reload so the
        # lifespan doesn't touch real Redis.
        with (
            patch.object(m, "init_clients"),
            patch.object(m, "close_clients"),
        ):
            deps._http_client = httpx.AsyncClient()
            deps._redis_rate_limit = rate_redis
            deps._redis_idempotency = idem_redis
            deps._rate_limiter = RateLimiter(redis=rate_redis, requests_per_minute=1000)
            deps._idempotency_store = IdempotencyStore(redis=idem_redis)

            # Use TestClient as a context manager so all requests share a single
            # event loop — required because FakeRedis binds to the loop on first use.
            with TestClient(application) as client:
                yield client

    # Cleanup
    deps._http_client = None
    deps._redis_rate_limit = None
    deps._redis_idempotency = None
    deps._rate_limiter = None
    deps._idempotency_store = None


def test_proxy_get_workflow_routes_to_workflow_service(gw_client):
    tenant_id = str(uuid.uuid4())
    wf_id = str(uuid.uuid4())
    with respx.mock:
        respx.get(f"http://workflow-service:8001/v1/workflows/{wf_id}").mock(
            return_value=httpx.Response(200, json={"id": wf_id, "name": "test"})
        )
        resp = gw_client.get(
            f"/v1/workflows/{wf_id}",
            headers=auth_headers(tenant_id),
        )
    assert resp.status_code == 200
    assert resp.json()["id"] == wf_id


def test_proxy_injects_x_internal_token_and_x_tenant_id(gw_client):
    tenant_id = str(uuid.uuid4())
    wf_id = str(uuid.uuid4())
    received: dict = {}

    def capture(request: httpx.Request) -> httpx.Response:
        received.update(dict(request.headers))
        return httpx.Response(200, json={})

    with respx.mock:
        respx.get(f"http://workflow-service:8001/v1/workflows/{wf_id}").mock(side_effect=capture)
        gw_client.get(f"/v1/workflows/{wf_id}", headers=auth_headers(tenant_id))

    assert "x-internal-token" in received
    assert received["x-tenant-id"] == tenant_id


def test_proxy_strips_authorization_header(gw_client):
    tenant_id = str(uuid.uuid4())
    wf_id = str(uuid.uuid4())
    received: dict = {}

    def capture(request: httpx.Request) -> httpx.Response:
        received.update(dict(request.headers))
        return httpx.Response(200, json={})

    with respx.mock:
        respx.get(f"http://workflow-service:8001/v1/workflows/{wf_id}").mock(side_effect=capture)
        gw_client.get(f"/v1/workflows/{wf_id}", headers=auth_headers(tenant_id))

    assert "authorization" not in received


def test_proxy_memory_search_routes_to_memory_service(gw_client):
    tenant_id = str(uuid.uuid4())
    with respx.mock:
        respx.post("http://memory-service:8002/v1/memory/search").mock(
            return_value=httpx.Response(
                200, json={"results": [], "cache_hit": False, "latency_ms": 5}
            )
        )
        resp = gw_client.post(
            "/v1/memory/search",
            json={"query": "test", "top_k": 5},
            headers=auth_headers(tenant_id),
        )
    assert resp.status_code == 200


def test_missing_auth_returns_401(gw_client):
    resp = gw_client.get(f"/v1/workflows/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_rate_limit_exceeded_returns_429(gw_client):
    import fakeredis
    import fakeredis.aioredis

    server = fakeredis.FakeServer()
    tight_redis = fakeredis.aioredis.FakeRedis(server=server)
    original = deps._rate_limiter
    deps._rate_limiter = RateLimiter(redis=tight_redis, requests_per_minute=2)

    tenant_id = str(uuid.uuid4())
    wf_id = str(uuid.uuid4())
    headers = auth_headers(tenant_id)

    with respx.mock:
        respx.get(f"http://workflow-service:8001/v1/workflows/{wf_id}").mock(
            return_value=httpx.Response(200, json={})
        )
        r1 = gw_client.get(f"/v1/workflows/{wf_id}", headers=headers)
        r2 = gw_client.get(f"/v1/workflows/{wf_id}", headers=headers)
        r3 = gw_client.get(f"/v1/workflows/{wf_id}", headers=headers)

    deps._rate_limiter = original
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


def test_idempotency_duplicate_returns_409(gw_client):
    tenant_id = str(uuid.uuid4())
    wf_id = str(uuid.uuid4())
    idem_key = "unique-op-abc123"

    with respx.mock:
        respx.post(f"http://workflow-service:8001/v1/workflows/{wf_id}/execute").mock(
            return_value=httpx.Response(202, json={"id": str(uuid.uuid4()), "status": "PENDING"})
        )
        r1 = gw_client.post(
            f"/v1/workflows/{wf_id}/execute",
            json={"inputs": {}},
            headers={**auth_headers(tenant_id), "Idempotency-Key": idem_key},
        )
        r2 = gw_client.post(
            f"/v1/workflows/{wf_id}/execute",
            json={"inputs": {}},
            headers={**auth_headers(tenant_id), "Idempotency-Key": idem_key},
        )

    assert r1.status_code == 202
    assert r2.status_code == 409


def test_downstream_404_is_passed_through(gw_client):
    tenant_id = str(uuid.uuid4())
    wf_id = str(uuid.uuid4())
    with respx.mock:
        respx.get(f"http://workflow-service:8001/v1/workflows/{wf_id}").mock(
            return_value=httpx.Response(404, json={"detail": "not found"})
        )
        resp = gw_client.get(f"/v1/workflows/{wf_id}", headers=auth_headers(tenant_id))
    assert resp.status_code == 404
