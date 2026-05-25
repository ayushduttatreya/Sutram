"""Force row-level security on all tenant-scoped tables.

ENABLE RLS only prevents non-owner roles from bypassing policies.
FORCE RLS ensures even the table owner (the app's DB role) goes through policies.

Revision ID: b2c3d4e5f6a1
Revises: 001
Create Date: 2026-05-25
"""

from __future__ import annotations

from alembic import op

revision: str = "b2c3d4e5f6a1"
down_revision: str = "001"
branch_labels = None
depends_on = None

_TABLES = (
    "memory_items",
    "memory_summaries",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
