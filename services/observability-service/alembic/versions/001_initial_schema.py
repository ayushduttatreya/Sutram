"""Initial schema: execution_traces, audit_log

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
    # ── execution_traces ──────────────────────────────────────────────
    op.create_table(
        "execution_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column(
            "start_time",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("step_name", sa.Text, nullable=True),
        sa.Column("step_index", sa.Integer, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Float, nullable=True),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("error_type", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("idx_traces_execution_id", "execution_traces", ["execution_id"])
    op.create_index("idx_traces_tenant_start", "execution_traces", ["tenant_id", "start_time"])
    op.execute(
        "CREATE INDEX idx_traces_start_time_brin ON execution_traces USING brin (start_time)"
    )

    # ── audit_log (append-only) ───────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
        ),
    )
    op.create_index("idx_audit_tenant_time", "audit_log", ["tenant_id", "timestamp"])
    # ADR-009: INSERT-only grant. Only effective when connecting as app_user (not superuser).
    op.execute("GRANT INSERT, SELECT ON audit_log TO app_user")


def downgrade() -> None:
    op.drop_table("execution_traces")
    op.drop_table("audit_log")
