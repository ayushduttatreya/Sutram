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


from sutram_core.models.workflow import Workflow, WorkflowDefinition, WorkflowStep, StepConfig
from sutram_core.models.execution import WorkflowExecution, ExecutionStatus
from sutram_core.models.checkpoint import Checkpoint
import uuid


def test_workflow_step_config_defaults():
    cfg = StepConfig(name="fetch")
    assert cfg.checkpoint_before is False
    assert cfg.max_retries == 3
    assert cfg.timeout_seconds == 300


def test_workflow_step_expensive_defaults_checkpoint():
    cfg = StepConfig(name="llm_call", checkpoint_before=True)
    assert cfg.checkpoint_before is True


def test_execution_status_transitions():
    assert ExecutionStatus.PENDING.value == "PENDING"
    assert ExecutionStatus.RUNNING.value == "RUNNING"
    assert ExecutionStatus.PAUSED.value == "PAUSED"
    assert ExecutionStatus.COMPLETED.value == "COMPLETED"
    assert ExecutionStatus.FAILED.value == "FAILED"
    assert ExecutionStatus.CANCELLED.value == "CANCELLED"


def test_checkpoint_schema_version_defaults_to_one():
    tenant_id = uuid.uuid4()
    execution_id = uuid.uuid4()
    cp = Checkpoint(
        execution_id=execution_id,
        tenant_id=tenant_id,
        step_name="fetch_sources",
        step_index=2,
        variables={"sources": ["a", "b"]},
        state={},
    )
    assert cp.schema_version == 1
    assert cp.step_name == "fetch_sources"


def test_checkpoint_migrate_to_current_applies_migrators():
    def migrate_v1_to_v2(variables):
        return {"new_key": variables["old_key"]}

    original_migrators = Checkpoint.migrators
    Checkpoint.migrators = {1: migrate_v1_to_v2}
    try:
        cp = Checkpoint(
            execution_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            step_name="step1",
            step_index=0,
            variables={"old_key": "value"},
            state={},
            schema_version=1,
        )
        migrated = cp.migrate_to_current()
        assert migrated.variables == {"new_key": "value"}
        assert migrated.schema_version == 2
    finally:
        Checkpoint.migrators = original_migrators


def test_checkpoint_migrate_to_current_no_op_when_no_migrators():
    cp = Checkpoint(
        execution_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        step_name="step1",
        step_index=0,
        variables={"key": "value"},
        state={},
        schema_version=1,
    )
    # No migrators registered — should return copy unchanged
    result = cp.migrate_to_current()
    assert result.variables == {"key": "value"}
    assert result.schema_version == 1


def test_checkpoint_migrate_to_current_chains_multiple_migrators():
    def v1_to_v2(variables):
        return {"b": variables["a"]}

    def v2_to_v3(variables):
        return {"c": variables["b"]}

    original_migrators = Checkpoint.migrators
    Checkpoint.migrators = {1: v1_to_v2, 2: v2_to_v3}
    try:
        cp = Checkpoint(
            execution_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            step_name="step1",
            step_index=0,
            variables={"a": "hello"},
            state={},
            schema_version=1,
        )
        migrated = cp.migrate_to_current()
        assert migrated.variables == {"c": "hello"}
        assert migrated.schema_version == 3
    finally:
        Checkpoint.migrators = original_migrators
