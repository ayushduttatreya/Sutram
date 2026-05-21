from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sutram_core.db.base import Base


class ExecutionTraceORM(Base):  # type: ignore[misc]
    """One row per span/event from the execution pipeline.

    MVP: plain Postgres with BRIN index on start_time.
    TimescaleDB hypertable deferred (requires image change to timescale/timescaledb-ha:pg16).
    No TimestampMixin — append-only data, no updated_at.
    """

    __tablename__ = "execution_traces"
    __table_args__ = (
        Index("idx_traces_execution_id", "execution_id"),
        Index("idx_traces_tenant_start", "tenant_id", "start_time"),
        # BRIN: compact index, fast for time-range queries on append-only table
        Index("idx_traces_start_time_brin", "start_time", postgresql_using="brin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    step_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLogORM(Base):  # type: ignore[misc]
    """Append-only audit record.

    No TimestampMixin — uses a plain `timestamp` column.
    No updated_at column by design (ADR-009).
    INSERT-only by DB role: GRANT INSERT, SELECT ON audit_log TO app_user.
    MVP limitation: services currently connect as superuser 'sutram', bypassing role grants.

    Note: 'metadata' is reserved on DeclarativeBase — Python attr is extra_metadata,
    DB column name is 'metadata' via name="metadata" in mapped_column.
    """

    __tablename__ = "audit_log"
    __table_args__ = (Index("idx_audit_tenant_time", "tenant_id", "timestamp"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # extra_metadata → DB column "metadata" (reserved name on DeclarativeBase)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, name="metadata", nullable=False, default=dict, server_default=text("{}")
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
