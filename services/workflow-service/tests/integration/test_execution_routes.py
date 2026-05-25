# tests/integration/test_execution_routes.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sutram_core.models.execution import ExecutionStatus


@pytest.fixture
def client():
    with patch("app.dependencies.init_db"), patch("app.dependencies.init_redis"):
        from importlib import reload

        import app.main as m

        reload(m)
        return TestClient(m.app)


def make_mock_execution(status: str = ExecutionStatus.PAUSED.value):
    from app.models.orm import WorkflowExecutionORM

    mock_ex = MagicMock(spec=WorkflowExecutionORM)
    mock_ex.id = uuid.uuid4()
    mock_ex.tenant_id = uuid.uuid4()
    mock_ex.workflow_id = uuid.uuid4()
    mock_ex.status = status
    mock_ex.error_message = None
    mock_ex.pause_reason = None
    return mock_ex


def test_pause_invalid_transition_returns_409(client):
    """Pausing a COMPLETED execution should return 409 Conflict."""
    mock_ex = make_mock_execution(ExecutionStatus.COMPLETED.value)
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_ex
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.dependencies._session_factory") as mock_factory:
        mock_factory.return_value = mock_ctx
        response = client.post(f"/v1/executions/{mock_ex.id}/pause")
        assert response.status_code == 409


def test_cancel_invalid_transition_returns_409(client):
    """Cancelling a RUNNING execution returns 409 — 'cancel' trigger is only valid from PAUSED."""
    mock_ex = make_mock_execution(ExecutionStatus.RUNNING.value)
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_ex
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.dependencies._session_factory") as mock_factory:
        mock_factory.return_value = mock_ctx
        response = client.post(f"/v1/executions/{mock_ex.id}/cancel")
        assert response.status_code == 409


def test_get_execution_not_found(client):
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
        response = client.get(f"/v1/executions/{uuid.uuid4()}")
        assert response.status_code == 404


def test_stream_execution_returns_event_stream(client):
    """SSE endpoint returns text/event-stream content type."""
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock(side_effect=Exception("BUSYGROUP"))
    mock_redis.xreadgroup = AsyncMock(return_value=[])
    mock_redis.xack = AsyncMock()

    with patch("app.dependencies._redis_streams", mock_redis):
        resp = client.get(f"/v1/executions/{uuid.uuid4()}/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
