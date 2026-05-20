# app/schemas/workflows.py
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sutram_core.models.workflow import WorkflowDefinition


class CreateWorkflowRequest(BaseModel):
    name: str
    description: str = ""
    definition: WorkflowDefinition


class WorkflowResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    tenant_id: UUID
    name: str
    description: str
    version: int


class ExecuteWorkflowRequest(BaseModel):
    inputs: dict[str, Any] = {}


class ExecutionResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    tenant_id: UUID
    workflow_id: UUID
    status: str
    error_message: str | None = None
    pause_reason: str | None = None
