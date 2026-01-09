"""Pytest configuration and fixtures for testing."""

import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Set test environment before importing app
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEBUG"] = "true"

from app.main import app
from app.db.database import Base, get_db


# Create test database engine
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=True
)

test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Provide session
    async with test_session_maker() as session:
        yield session

    # Drop tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden database dependency."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_topic():
    """Sample coaching topic for tests."""
    return "I want to speak up more in meetings but I keep staying quiet"


@pytest.fixture
def sample_messages():
    """Sample conversation messages for tests."""
    return [
        "Last week in a design review. I spotted a flaw in the approach but someone senior was presenting, so I just stayed quiet.",
        "I didn't want to seem like I was challenging them. What if I was wrong?",
        "They'd think I'm overstepping. Or I'd look stupid if my concern wasn't valid.",
        "It caused a two-day delay when we found it later in implementation.",
        "I guess... they'd explain why it wasn't actually a problem. And I'd learn something. That's not that bad.",
        "No. I want to be seen as someone who contributes.",
        "I could commit to raising one question or concern in tomorrow's standup.",
        "8",
        "Having the specific thing I want to say ready beforehand.",
        "Yes."
    ]
