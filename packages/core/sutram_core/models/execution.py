# packages/core/sutram_core/models/execution.py
from __future__ import annotations
from enum import Enum
from typing import Any
import uuid
from pydantic import BaseModel
from .base import SutramBaseModel


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionContext(BaseModel):
    execution_id: uuid.UUID
    tenant_id: uuid.UUID
    workflow_id: uuid.UUID
    variables: dict[str, Any] = {}
    current_step_index: int = 0
    total_cost_usd: float = 0.0
    llm_calls: int = 0


class WorkflowExecution(SutramBaseModel):
    tenant_id: uuid.UUID
    workflow_id: uuid.UUID
    status: ExecutionStatus = ExecutionStatus.PENDING
    context: ExecutionContext
    error_message: str | None = None
    pause_reason: str | None = None
