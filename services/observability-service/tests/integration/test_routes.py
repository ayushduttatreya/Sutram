# tests/integration/test_routes.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

VALID_TOKEN = "dev-internal-token-change-in-production"
VALID_TENANT = str(uuid.uuid4())
HEADERS = {"X-Internal-Token": VALID_TOKEN, "X-Tenant-ID": VALID_TENANT}


def test_get_traces_returns_empty_spans():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.get_redis_streams", return_value=MagicMock()),
        patch("app.main.run_consumer_loop", new_callable=AsyncMock),
        patch("app.dependencies._session_factory") as mock_factory,
    ):
        mock_factory.return_value = mock_ctx
        from app.main import create_app

        with TestClient(create_app()) as client:
            resp = client.get(f"/v1/traces/{uuid.uuid4()}", headers=HEADERS)

    assert resp.status_code == 200
    assert resp.json()["spans"] == []


def test_get_audit_logs_returns_empty():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.get_redis_streams", return_value=MagicMock()),
        patch("app.main.run_consumer_loop", new_callable=AsyncMock),
        patch("app.dependencies._session_factory") as mock_factory,
    ):
        mock_factory.return_value = mock_ctx
        from app.main import create_app

        with TestClient(create_app()) as client:
            resp = client.get("/v1/audit-logs", headers=HEADERS)

    assert resp.status_code == 200
    assert resp.json()["records"] == []


def test_missing_internal_token_returns_422():
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.get_redis_streams", return_value=MagicMock()),
        patch("app.main.run_consumer_loop", new_callable=AsyncMock),
        patch("app.dependencies._session_factory") as mock_factory,
    ):
        mock_factory.return_value = mock_ctx
        from app.main import create_app

        with TestClient(create_app()) as client:
            resp = client.get(
                f"/v1/traces/{uuid.uuid4()}",
                headers={"X-Tenant-ID": VALID_TENANT},
            )
    assert resp.status_code == 422


def test_prometheus_metrics_endpoint_accessible():
    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.get_redis_streams", return_value=MagicMock()),
        patch("app.main.run_consumer_loop", new_callable=AsyncMock),
    ):
        from app.main import create_app

        with TestClient(create_app()) as client:
            resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
