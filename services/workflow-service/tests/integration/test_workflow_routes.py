# tests/integration/test_workflow_routes.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("app.dependencies.init_db"), patch("app.dependencies.init_redis"):
        from importlib import reload

        import app.main as m

        reload(m)
        return TestClient(m.app)


def test_get_workflow_not_found(client):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.dependencies._session_factory") as mock_factory:
        mock_factory.return_value = mock_ctx
        response = client.get(f"/v1/workflows/{uuid.uuid4()}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Workflow not found"
