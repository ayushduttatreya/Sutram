# services/memory-service/app/models/orm.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Index,
    Integer, Text, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from sutram_core.db.base import Base, TimestampMixin


class MemoryItemORM(Base, TimestampMixin):  # type: ignore[misc]
    __tablename__ = "memory_items"
    __table_args__ = (
        Index("idx_memory_items_tenant_id", "tenant_id"),
        Index(
            "idx_memory_items_tenant_compressed",
            "tenant_id", "compressed",
            postgresql_where=text("compressed = false"),
        ),
        Index("idx_memory_items_tenant_type", "tenant_id", "memory_type"),
        Index(
            "idx_memory_items_tenant_created",
            "tenant_id", "created_at",
            postgresql_where=text("compressed = false"),
        ),
        CheckConstraint(
            "memory_type IN ('episodic', 'semantic', 'procedural')",
            name="ck_memory_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    memory_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    # DB column name is "metadata" — Python attr is "extra_metadata" because
    # "metadata" is reserved by SQLAlchemy's DeclarativeBase as the MetaData object.
    # Pydantic response schemas must use field name "extra_metadata" with from_attributes=True.
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, name="metadata", nullable=False, default=dict, server_default=text("{}")
    )
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )
    access_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    retention_policy: Mapped[str] = mapped_column(
        Text, nullable=False, default="90d", server_default=text("'90d'")
    )
    compressed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE")
    )


class MemorySummaryORM(Base, TimestampMixin):  # type: ignore[misc]
    __tablename__ = "memory_summaries"
    __table_args__ = (
        Index("idx_memory_summaries_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    original_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default=text("'{}'")
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
