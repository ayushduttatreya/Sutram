# services/workflow-service/app/models/orm.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sutram_core.db.base import Base, TimestampMixin


class TenantORM(Base, TimestampMixin):  # type: ignore[misc]
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("{}")
    )

    workflows: Mapped[list[WorkflowORM]] = relationship(back_populates="tenant")
    executions: Mapped[list[WorkflowExecutionORM]] = relationship(back_populates="tenant")


class WorkflowORM(Base, TimestampMixin):  # type: ignore[misc]
    __tablename__ = "workflows"
    __table_args__ = (Index("idx_workflows_tenant_id", "tenant_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    tenant: Mapped[TenantORM] = relationship(back_populates="workflows")
    executions: Mapped[list[WorkflowExecutionORM]] = relationship(back_populates="workflow")


class WorkflowExecutionORM(Base, TimestampMixin):  # type: ignore[misc]
    __tablename__ = "workflow_executions"
    __table_args__ = (
        Index("idx_executions_tenant_id", "tenant_id"),
        Index("idx_executions_status", "status"),
        Index(
            "idx_executions_heartbeat",
            "last_heartbeat",
            postgresql_where=text("status = 'RUNNING'"),
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','PAUSED','COMPLETED','FAILED','CANCELLED')",
            name="ck_execution_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("{}")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[TenantORM] = relationship(back_populates="executions")
    workflow: Mapped[WorkflowORM] = relationship(back_populates="executions")
    checkpoints: Mapped[list[CheckpointORM]] = relationship(back_populates="execution")


class CheckpointORM(Base):  # type: ignore[misc]
    """Append-only — no updated_at. Checkpoints are immutable once written."""

    __tablename__ = "checkpoints"
    __table_args__ = (
        Index("idx_checkpoints_execution_id", "execution_id"),
        Index("idx_checkpoints_execution_latest", "execution_id", "step_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    step_name: Mapped[str] = mapped_column(Text, nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    variables: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("{}")
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    execution: Mapped[WorkflowExecutionORM] = relationship(back_populates="checkpoints")


class WebhookSubscriptionORM(Base, TimestampMixin):  # type: ignore[misc]
    __tablename__ = "webhook_subscriptions"
    __table_args__ = (
        Index(
            "idx_webhook_subs_tenant_active",
            "tenant_id",
            postgresql_where=text("active = TRUE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # AES-GCM encrypted secret — must be decryptable for HMAC signing (not a hash)
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    events: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=lambda: ["execution.completed"]
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    deliveries: Mapped[list[WebhookDeliveryORM]] = relationship(back_populates="subscription")


class WebhookDeliveryORM(Base, TimestampMixin):  # type: ignore[misc]
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("idx_webhook_deliveries_tenant", "tenant_id"),
        Index(
            "idx_webhook_deliveries_retry",
            "next_retry_at",
            postgresql_where=text("status = 'pending'"),
        ),
        CheckConstraint(
            "status IN ('pending','delivered','failed','dead_lettered')",
            name="ck_delivery_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    subscription: Mapped[WebhookSubscriptionORM] = relationship(back_populates="deliveries")
