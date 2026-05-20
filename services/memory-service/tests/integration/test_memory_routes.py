import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

VALID_TENANT = str(uuid.uuid4())
VALID_HEADERS = {
    "X-Internal-Token": "dev-internal-token-change-in-production",
    "X-Tenant-ID": VALID_TENANT,
}


@pytest.fixture
def client():
    with (
        patch("app.dependencies.init_db"),
        patch("app.dependencies.init_redis"),
        patch("app.dependencies.init_embedding"),
    ):
        from importlib import reload

        import app.main as m

        reload(m)
        return TestClient(m.app)


def _make_mock_session():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


def test_get_memory_item_not_found(client):
    mock_ctx = _make_mock_session()

    with patch("app.dependencies._session_factory") as mock_factory:
        mock_factory.return_value = mock_ctx
        response = client.get(f"/v1/memory/items/{uuid.uuid4()}", headers=VALID_HEADERS)
        assert response.status_code == 404


def test_forget_memory_not_found(client):
    mock_ctx = _make_mock_session()
    mock_redis = AsyncMock()
    # scan returns (cursor=0, keys=[]) so loop exits immediately
    mock_redis.scan = AsyncMock(return_value=(0, []))
    mock_redis.delete = AsyncMock()

    with (
        patch("app.dependencies._session_factory") as mock_factory,
        patch("app.dependencies._redis_cache", mock_redis),
    ):
        mock_factory.return_value = mock_ctx
        response = client.delete(f"/v1/memory/items/{uuid.uuid4()}", headers=VALID_HEADERS)
        assert response.status_code == 404


def test_missing_internal_token_returns_422(client):
    mock_ctx = _make_mock_session()

    with patch("app.dependencies._session_factory") as mock_factory:
        mock_factory.return_value = mock_ctx
        response = client.get(
            f"/v1/memory/items/{uuid.uuid4()}",
            headers={"X-Tenant-ID": VALID_TENANT},
        )
        assert response.status_code == 422
