# packages/core/sutram_core/models/workflow.py
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from .base import SutramBaseModel


class StepConfig(BaseModel):
    name: str
    checkpoint_before: bool = False
    max_retries: int = 3
    timeout_seconds: int = 300
    retry_backoff: Literal["exponential", "linear", "fixed"] = "exponential"


class WorkflowStep(BaseModel):
    config: StepConfig
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinition(BaseModel):
    steps: list[WorkflowStep]
    version: int = 1


class Workflow(SutramBaseModel):
    tenant_id: uuid.UUID
    name: str
    description: str = ""
    definition: WorkflowDefinition
    version: int = 1
