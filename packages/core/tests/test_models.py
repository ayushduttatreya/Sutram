import pytest
from datetime import datetime, timezone
from uuid import UUID
from sutram_core.models.tenant import Tenant, TenantSettings


def test_tenant_has_required_fields():
    t = Tenant(name="acme")
    assert isinstance(t.id, UUID)
    assert t.name == "acme"
    assert isinstance(t.created_at, datetime)
    assert t.settings == TenantSettings()


def test_tenant_settings_defaults():
    s = TenantSettings()
    assert s.max_concurrent_executions == 10
    assert s.max_cost_per_execution_usd == 10.0
    assert s.max_cost_per_day_usd == 100.0
    assert s.max_storage_gb == 100


def test_tenant_settings_custom():
    s = TenantSettings(max_concurrent_executions=50)
    assert s.max_concurrent_executions == 50


def test_tenant_ids_are_unique():
    t1 = Tenant(name="a")
    t2 = Tenant(name="b")
    assert t1.id != t2.id


def test_tenant_created_at_is_timezone_aware():
    t = Tenant(name="acme")
    assert t.created_at.tzinfo is not None


def test_tenant_settings_not_shared_across_instances():
    t1 = Tenant(name="a")
    t2 = Tenant(name="b")
    assert t1.settings is not t2.settings
