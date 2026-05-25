"""Add definition_snapshot column to workflow_executions.

Snapshots the workflow definition at execution creation time so that
in-flight executions are not affected by subsequent workflow updates.

Revision ID: 003
Revises: a1b2c3d4e5f6
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_executions",
        sa.Column("definition_snapshot", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_executions", "definition_snapshot")
