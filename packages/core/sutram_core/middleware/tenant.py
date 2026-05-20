from __future__ import annotations
from typing import Any
from sqlalchemy import text


async def set_tenant_context(
    session: Any,
    tenant_id: str,
) -> None:
    """Set the tenant context on a database session for row-level security.

    Must be called after auth and before any database queries.
    Uses SET LOCAL so the context is scoped to the current transaction
    (required for PgBouncer transaction pooling mode).
    """
    await session.execute(
        text("SET LOCAL app.current_tenant_id = :tid"),
        {"tid": tenant_id},
    )
