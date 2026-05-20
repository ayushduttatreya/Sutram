# services/workflow-service/alembic/versions/001_initial_schema.py
"""Initial schema: tenants, workflows, executions, checkpoints, webhooks

Revision ID: 001
Revises:
Create Date: 2026-05-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── tenants ───────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # ── workflows ─────────────────────────────────────────────────────
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("definition", postgresql.JSONB, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("idx_workflows_tenant_id", "workflows", ["tenant_id"])

    # ── workflow_executions ───────────────────────────────────────────
    op.create_table(
        "workflow_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text, nullable=False, server_default="PENDING"),
        sa.Column("context", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("pause_reason", sa.Text, nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','PAUSED','COMPLETED','FAILED','CANCELLED')",
            name="ck_execution_status",
        ),
    )
    op.create_index("idx_executions_tenant_id", "workflow_executions", ["tenant_id"])
    op.create_index("idx_executions_status", "workflow_executions", ["status"])
    op.create_index(
        "idx_executions_heartbeat",
        "workflow_executions",
        ["last_heartbeat"],
        postgresql_where=sa.text("status = 'RUNNING'"),
    )

    # ── checkpoints ───────────────────────────────────────────────────
    op.create_table(
        "checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_name", sa.Text, nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("variables", postgresql.JSONB, nullable=False),
        sa.Column("state", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("idx_checkpoints_execution_id", "checkpoints", ["execution_id"])
    op.create_index(
        "idx_checkpoints_execution_latest", "checkpoints", ["execution_id", "step_index"]
    )

    # ── webhook_subscriptions ─────────────────────────────────────────
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("secret_encrypted", sa.Text, nullable=False),
        sa.Column(
            "events",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="'{execution.completed}'",
        ),
        sa.Column("active", sa.Boolean, nullable=False, server_default="TRUE"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_webhook_subs_tenant_active",
        "webhook_subscriptions",
        ["tenant_id"],
        postgresql_where=sa.text("active = TRUE"),
    )

    # ── webhook_deliveries ────────────────────────────────────────────
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_code", sa.Integer, nullable=True),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending','delivered','failed','dead_lettered')",
            name="ck_delivery_status",
        ),
    )
    op.create_index("idx_webhook_deliveries_tenant", "webhook_deliveries", ["tenant_id"])
    op.create_index(
        "idx_webhook_deliveries_retry",
        "webhook_deliveries",
        ["next_retry_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # ── Row-level security ────────────────────────────────────────────
    for table in (
        "workflows",
        "workflow_executions",
        "checkpoints",
        "webhook_subscriptions",
        "webhook_deliveries",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid) "
            f"WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)"
        )


def downgrade() -> None:
    for table in (
        "webhook_deliveries",
        "webhook_subscriptions",
        "checkpoints",
        "workflow_executions",
        "workflows",
        "tenants",
    ):
        op.drop_table(table)
