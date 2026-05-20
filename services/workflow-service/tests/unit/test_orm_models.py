# tests/unit/test_orm_models.py
from app.models.orm import (
    CheckpointORM,
    TenantORM,
    WebhookDeliveryORM,
    WebhookSubscriptionORM,
    WorkflowExecutionORM,
    WorkflowORM,
)


def test_all_orm_models_have_tablenames():
    assert TenantORM.__tablename__ == "tenants"
    assert WorkflowORM.__tablename__ == "workflows"
    assert WorkflowExecutionORM.__tablename__ == "workflow_executions"
    assert CheckpointORM.__tablename__ == "checkpoints"
    assert WebhookSubscriptionORM.__tablename__ == "webhook_subscriptions"
    assert WebhookDeliveryORM.__tablename__ == "webhook_deliveries"


def test_checkpoint_has_no_updated_at():
    """Checkpoints are append-only — no updated_at column."""
    cols = {c.key for c in CheckpointORM.__table__.columns}
    assert "created_at" in cols
    assert "updated_at" not in cols


def test_execution_status_check_constraint():
    constraints = {c.name for c in WorkflowExecutionORM.__table__.constraints}
    assert "ck_execution_status" in constraints


def test_webhook_subscription_has_secret_encrypted_not_hash():
    """Secret must be stored encrypted (AES-GCM), never as a hash."""
    cols = {c.key for c in WebhookSubscriptionORM.__table__.columns}
    assert "secret_encrypted" in cols
    assert "secret_hash" not in cols


def test_all_tenant_tables_have_tenant_id():
    for model in [
        WorkflowORM,
        WorkflowExecutionORM,
        CheckpointORM,
        WebhookSubscriptionORM,
        WebhookDeliveryORM,
    ]:
        cols = {c.key for c in model.__table__.columns}
        assert "tenant_id" in cols, f"{model.__tablename__} missing tenant_id"
