# packages/core/tests/test_db_session.py
import pytest
from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column
from sutram_core.db.base import Base, TimestampMixin
from sutram_core.db.session import create_engine, create_session_factory, get_session


class SampleModel(Base, TimestampMixin):
    __tablename__ = "sample_items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


@pytest.fixture
async def db_session_factory():
    """In-memory SQLite engine + session factory for tests."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    yield factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_session_factory_creates_sessions(db_session_factory):
    """Session factory produces usable AsyncSession instances."""
    async for session in get_session(db_session_factory):
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_session_commits_on_success(db_session_factory):
    """Data written in a session is committed when no exception is raised."""
    async for session in get_session(db_session_factory):
        session.add(SampleModel(id="1", name="hello"))

    # Verify in a new session
    async for session in get_session(db_session_factory):
        result = await session.execute(text("SELECT name FROM sample_items WHERE id='1'"))
        assert result.scalar() == "hello"


@pytest.mark.asyncio
async def test_session_rolls_back_on_exception(db_session_factory):
    """Data written in a session is rolled back when an exception is raised."""
    with pytest.raises(ValueError):
        async for session in get_session(db_session_factory):
            session.add(SampleModel(id="2", name="should-not-persist"))
            raise ValueError("simulated failure")

    # Verify nothing was committed
    async for session in get_session(db_session_factory):
        result = await session.execute(text("SELECT COUNT(*) FROM sample_items WHERE id='2'"))
        assert result.scalar() == 0


@pytest.mark.asyncio
async def test_expire_on_commit_false(db_session_factory):
    """expire_on_commit=False means ORM object attributes remain readable after commit.

    With expire_on_commit=True, accessing obj.name after commit in async context
    raises MissingGreenlet (no lazy loading in async). This test verifies the
    attribute is still accessible in-memory without a new DB round-trip.
    """
    async with db_session_factory() as session:
        obj = SampleModel(id="3", name="check-expiry")
        session.add(obj)
        await session.commit()
        # With expire_on_commit=True this would raise MissingGreenlet in async
        assert obj.name == "check-expiry"
        assert obj.id == "3"
