"""Pytest test configuration and fixtures."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.session import get_db
from app.main import app

# Use NullPool for tests so asyncpg connections do not leak across function-scoped event loops
test_engine = create_async_engine(
    settings.async_database_url,
    poolclass=NullPool,
)

test_session_maker = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def override_get_db() -> AsyncIterator[AsyncSession]:
    """Dependency override providing an isolated test database session."""
    async with test_session_maker() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Provide an asynchronous database session for tests."""
    async with test_session_maker() as session:
        yield session


@pytest.fixture(autouse=True)
async def clean_database() -> AsyncIterator[None]:
    """Clean all domain tables before each test to guarantee test isolation."""
    async with test_session_maker() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE "
                "service_dependencies, "
                "team_memberships, "
                "organization_memberships, "
                "services, "
                "teams, "
                "organizations, "
                "users "
                "CASCADE;"
            )
        )
        await session.commit()
    yield


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Provide an asynchronous HTTP client configured for the FastAPI test application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
