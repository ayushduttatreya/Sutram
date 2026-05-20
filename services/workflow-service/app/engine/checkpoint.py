# app/engine/checkpoint.py
from __future__ import annotations
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sutram_core.models.workflow import StepConfig
from app.models.orm import CheckpointORM


class CheckpointManager:
    """Writes and reads execution checkpoints using the current DB session.

    Write pattern: session.add() + session.flush() inside the caller's transaction.
    The caller (executor) is responsible for the surrounding transaction commit.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def should_checkpoint(self, step: StepConfig) -> bool:
        """Return True if a checkpoint should be written before this step."""
        return step.checkpoint_before

    async def write(
        self,
        execution_id: uuid.UUID,
        tenant_id: uuid.UUID,
        step_name: str,
        step_index: int,
        variables: dict[str, Any],
        state: dict[str, Any] | None = None,
        schema_version: int = 1,
    ) -> CheckpointORM:
        """Write checkpoint to DB via current session. Caller must commit the transaction."""
        orm = CheckpointORM(
            id=uuid.uuid4(),
            execution_id=execution_id,
            tenant_id=tenant_id,
            step_name=step_name,
            step_index=step_index,
            variables=variables,
            state=state or {},
            schema_version=schema_version,
        )
        self._session.add(orm)
        await self._session.flush()
        return orm

    async def get_latest(self, execution_id: uuid.UUID) -> CheckpointORM | None:
        """Load the most recent checkpoint for an execution (by highest step_index)."""
        result = await self._session.execute(
            select(CheckpointORM)
            .where(CheckpointORM.execution_id == execution_id)
            .order_by(CheckpointORM.step_index.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
