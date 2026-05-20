# tests/unit/test_celery_tasks.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.tasks.celery_app import celery_app


def test_celery_app_name():
    assert celery_app.main == "workflow-service"


def test_celery_acks_late():
    assert celery_app.conf.task_acks_late is True


def test_celery_reject_on_worker_lost():
    assert celery_app.conf.task_reject_on_worker_lost is True


def test_celery_prefetch_multiplier():
    assert celery_app.conf.worker_prefetch_multiplier == 1


def test_execute_workflow_task_registered():
    assert "workflow.execute" in celery_app.tasks


def test_execute_workflow_task_max_retries():
    task = celery_app.tasks["workflow.execute"]
    assert task.max_retries == 0


@pytest.mark.asyncio
async def test_run_returns_silently_when_execution_not_found():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.dependencies.get_db_session_context", return_value=mock_ctx):
        from app.tasks.execute import _run

        await _run(str(uuid.uuid4()))  # should complete without raising


def test_deliver_webhook_task_registered():
    assert "webhook.deliver" in celery_app.tasks


def test_deliver_webhook_task_max_retries():
    task = celery_app.tasks["webhook.deliver"]
    assert task.max_retries == 5  # len(RETRY_DELAYS)


@pytest.mark.asyncio
async def test_run_returns_silently_when_execution_already_terminal():
    from app.models.orm import WorkflowExecutionORM
    from sutram_core.models.execution import ExecutionStatus

    mock_execution = MagicMock(spec=WorkflowExecutionORM)
    mock_execution.status = ExecutionStatus.COMPLETED.value

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_execution
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.dependencies.get_db_session_context", return_value=mock_ctx):
        from app.tasks.execute import _run

        await _run(str(uuid.uuid4()))  # should complete without raising
