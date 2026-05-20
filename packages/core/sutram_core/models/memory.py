# packages/core/sutram_core/models/memory.py
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from .base import SutramBaseModel


class MemoryType(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryItem(SutramBaseModel):
    tenant_id: uuid.UUID
    memory_type: MemoryType
    content: str
    embedding: list[float] = Field(default_factory=list)
    embedding_model: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    access_count: int = 0
    retention_policy: str = "90d"
    compressed: bool = False


class MemorySummary(SutramBaseModel):
    tenant_id: uuid.UUID
    summary: str
    original_ids: list[uuid.UUID] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)
    embedding_model: str = ""
