import json
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    event_type: str
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    def to_stream_dict(self) -> dict[str, str]:
        """Serialize for Redis Streams XADD — all values must be flat strings.
        Nested dicts/lists are JSON-encoded so consumers can deserialize them."""
        result = {}
        for k, v in self.model_dump().items():
            if isinstance(v, (dict, list)):
                result[k] = json.dumps(v)
            else:
                result[k] = str(v)
        return result
