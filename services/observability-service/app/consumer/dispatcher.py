"""Deserializes Redis Streams message dicts into typed Pydantic event objects.

All stream values are strings. We dispatch on event_type to the correct subclass.
Pydantic v2 coerces string numbers ("500") to int/float where the field type requires it.
"""
from __future__ import annotations

from sutram_core.events.base import BaseEvent
from sutram_core.events.execution import (
    ExecutionStartedEvent,
    StepCompletedEvent,
    StepFailedEvent,
    ExecutionCompletedEvent,
    ExecutionPausedEvent,
)
from sutram_core.events.memory import MemoryWrittenEvent, MemorySearchedEvent

_REGISTRY: dict[str, type[BaseEvent]] = {
    "execution.started": ExecutionStartedEvent,
    "execution.step.completed": StepCompletedEvent,
    "execution.step.failed": StepFailedEvent,
    "execution.completed": ExecutionCompletedEvent,
    "execution.paused": ExecutionPausedEvent,
    "memory.written": MemoryWrittenEvent,
    "memory.searched": MemorySearchedEvent,
}


class UnknownEventType(Exception):
    """Raised when a stream message has an unrecognised event_type."""


def parse_event(data: dict[str, str]) -> BaseEvent:
    """Construct a typed Pydantic event from a Redis Streams message dict."""
    event_type = data.get("event_type", "")
    cls = _REGISTRY.get(event_type)
    if cls is None:
        raise UnknownEventType(f"Unknown event_type: {event_type!r}")
    return cls.model_validate(data)
