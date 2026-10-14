"""Pytest test configuration and fixtures."""

from collections.abc import AsyncIterator, Callable

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


@pytest.fixture
def auth_headers() -> Callable[[str], dict[str, str]]:
    """Return a helper that formats an Authorization Bearer header for a given token string."""

    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture
def test_jwt_settings(monkeypatch: pytest.MonkeyPatch) -> dict[str, str | int]:
    """Provide verified test-specific JWT settings with high-entropy test secret."""
    test_secret = "test-secret-key-with-sufficient-entropy-for-testing-256bits"
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", test_secret)
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15)
    monkeypatch.setattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7)
    return {
        "JWT_SECRET_KEY": test_secret,
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": 15,
        "REFRESH_TOKEN_EXPIRE_DAYS": 7,
    }


@pytest.fixture
def sample_user_data() -> dict[str, str]:
    """Provide sample user registration and credential data meeting password policy."""
    return {
        "email": "test.responder@incidenthub.io",
        "password": "StrongPassword123!",
        "display_name": "Test Responder",
    }
