import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class SutramBaseModel(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
