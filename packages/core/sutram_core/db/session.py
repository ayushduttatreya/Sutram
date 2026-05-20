# packages/core/sutram_core/db/session.py
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool


def create_engine(database_url: str, use_nullpool: bool = False) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    use_nullpool=True: Use NullPool — required when connecting via PgBouncer in
    transaction-pooling mode. PgBouncer manages the connection pool itself;
    SQLAlchemy's pool and pool_pre_ping are redundant and cause errors in that mode.

    use_nullpool=False (default): Use SQLAlchemy's built-in pool with pre-ping.
    Suitable for direct Postgres connections (dev/test without PgBouncer).

    SQLite (in-memory) always uses StaticPool so that all sessions share the same
    connection and see each other's data — NullPool would give each session its own
    independent in-memory database.
    """
    is_sqlite = database_url.lower().startswith("sqlite")

    if is_sqlite:
        return create_async_engine(
            database_url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )

    if use_nullpool:
        return create_async_engine(database_url, poolclass=NullPool)

    return create_async_engine(
        database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the given engine."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Async generator dependency. Yields a DB session.

    Commits on successful exit, rolls back on exception.
    AsyncSession.__aexit__ only calls close(), not commit() — explicit commit required here.
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
