"""Initial schema: memory_items and memory_summaries

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
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── memory_items ──────────────────────────────────────────────────
    op.create_table(
        "memory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_type", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text, nullable=False),  # converted to vector below
        sa.Column("embedding_model", sa.Text, nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "accessed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("access_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("retention_policy", sa.Text, nullable=False, server_default="'90d'"),
        sa.Column("compressed", sa.Boolean, nullable=False, server_default="FALSE"),
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
            "memory_type IN ('episodic', 'semantic', 'procedural')",
            name="ck_memory_type",
        ),
    )
    op.execute(  # noqa: E501
        "ALTER TABLE memory_items ALTER COLUMN embedding"
        " TYPE vector(1536) USING embedding::vector(1536)"
    )

    op.create_index("idx_memory_items_tenant_id", "memory_items", ["tenant_id"])
    op.create_index(
        "idx_memory_items_tenant_compressed",
        "memory_items",
        ["tenant_id", "compressed"],
        postgresql_where=sa.text("compressed = false"),
    )
    op.create_index("idx_memory_items_tenant_type", "memory_items", ["tenant_id", "memory_type"])
    op.create_index(
        "idx_memory_items_tenant_created",
        "memory_items",
        ["tenant_id", "created_at"],
        postgresql_where=sa.text("compressed = false"),
    )
    op.execute(
        "CREATE INDEX idx_memory_items_embedding ON memory_items "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64) "
        "WHERE compressed = false"
    )

    # ── memory_summaries ──────────────────────────────────────────────
    op.create_table(
        "memory_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column(
            "original_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="'{}'",
        ),
        sa.Column("embedding", sa.Text, nullable=False),
        sa.Column("embedding_model", sa.Text, nullable=False),
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
    op.execute(
        "ALTER TABLE memory_summaries ALTER COLUMN embedding"
        " TYPE vector(1536) USING embedding::vector(1536)"
    )

    op.create_index("idx_memory_summaries_tenant_id", "memory_summaries", ["tenant_id"])
    op.execute(
        "CREATE INDEX idx_memory_summaries_embedding ON memory_summaries "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )

    # ── Row-level security ────────────────────────────────────────────
    for table in ("memory_items", "memory_summaries"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid) "
            f"WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)"
        )


def downgrade() -> None:
    op.drop_table("memory_summaries")
    op.drop_table("memory_items")
