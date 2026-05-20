from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from sutram_core.models.memory import MemoryType


class MemoryItemCreate(BaseModel):
    content: str
    memory_type: MemoryType
    extra_metadata: dict[str, Any] = Field(default_factory=dict)
    retention_policy: str = "90d"


class MemoryBatchCreate(BaseModel):
    items: list[MemoryItemCreate]


class MemoryItemResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    tenant_id: UUID
    memory_type: str
    content: str
    embedding_model: str
    # NOTE: ORM attr is "extra_metadata" (DB column is "metadata")
    extra_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    accessed_at: datetime
    access_count: int
    retention_policy: str
    compressed: bool


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5
    memory_types: list[MemoryType] | None = None


class MemorySearchResult(BaseModel):
    item: MemoryItemResponse
    score: float
    similarity: float


class MemorySearchResponse(BaseModel):
    results: list[MemorySearchResult]
    cache_hit: bool
    latency_ms: int
