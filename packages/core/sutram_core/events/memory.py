import uuid
from typing import Literal
from .base import BaseEvent
from sutram_core.models.memory import MemoryType


class MemoryWrittenEvent(BaseEvent):
    event_type: Literal["memory.written"] = "memory.written"
    memory_item_id: uuid.UUID
    memory_type: MemoryType


class MemorySearchedEvent(BaseEvent):
    event_type: Literal["memory.searched"] = "memory.searched"
    query_hash: str
    results_count: int
    latency_ms: int
    cache_hit: bool = False
