import uuid
from typing import Any, Literal
from pydantic import Field
from .base import BaseEvent
from sutram_core.models.execution import ExecutionStatus


class ExecutionStartedEvent(BaseEvent):
    event_type: Literal["execution.started"] = "execution.started"
    execution_id: uuid.UUID
    workflow_id: uuid.UUID


class StepCompletedEvent(BaseEvent):
    event_type: Literal["execution.step.completed"] = "execution.step.completed"
    execution_id: uuid.UUID
    workflow_id: uuid.UUID
    step_name: str
    step_index: int
    duration_ms: int
    cost_usd: float = 0.0
    outputs: dict[str, Any] = Field(default_factory=dict)


class StepFailedEvent(BaseEvent):
    event_type: Literal["execution.step.failed"] = "execution.step.failed"
    execution_id: uuid.UUID
    workflow_id: uuid.UUID
    step_name: str
    step_index: int
    error_type: str
    error_message: str
    will_retry: bool = False


class ExecutionCompletedEvent(BaseEvent):
    event_type: Literal["execution.completed"] = "execution.completed"
    execution_id: uuid.UUID
    workflow_id: uuid.UUID
    status: ExecutionStatus
    total_duration_ms: int
    total_cost_usd: float
    total_steps: int


class ExecutionPausedEvent(BaseEvent):
    event_type: Literal["execution.paused"] = "execution.paused"
    execution_id: uuid.UUID
    workflow_id: uuid.UUID
    pause_reason: str
    paused_at_step: str
