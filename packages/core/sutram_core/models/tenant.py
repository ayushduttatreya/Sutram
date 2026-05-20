from pydantic import BaseModel, Field

from .base import SutramBaseModel


class TenantSettings(BaseModel):
    max_concurrent_executions: int = 10
    max_cost_per_execution_usd: float = 10.0
    max_cost_per_day_usd: float = 100.0
    max_storage_gb: int = 100
    rate_limit_requests_per_minute: int = 1000


class Tenant(SutramBaseModel):
    name: str
    settings: TenantSettings = Field(default_factory=TenantSettings)
