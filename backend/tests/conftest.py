"""Pytest test configuration and fixtures."""

import uuid
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
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.user import User


def is_postgres_available() -> bool:
    """Verify if PostgreSQL server is online and accepting connections for the test database."""
    try:
        import psycopg2

        conn = psycopg2.connect(
            settings.sync_database_url,
            connect_timeout=1,
        )
        conn.close()
        return True
    except Exception:
        return False


POSTGRES_AVAILABLE = is_postgres_available()

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
    if not POSTGRES_AVAILABLE:
        yield
        return
    try:
        async with test_session_maker() as session:
            await session.execute(
                text(
                    "TRUNCATE TABLE "
                    "refresh_tokens, "
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
    except Exception:
        yield
        return
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
async def test_user(db_session: AsyncSession) -> AsyncIterator[User]:
    """Provide a persisted test user for domain and integration tests."""
    if not POSTGRES_AVAILABLE:
        pytest.skip("PostgreSQL database unavailable or authentication failed")
    user = User(
        id=uuid.uuid4(),
        email="test.owner@incidenthub.io",
        display_name="Test Owner",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user


@pytest.fixture
def test_token(test_user: User) -> str:
    """Generate a valid signed access token for test_user."""
    return create_access_token(user_id=test_user.id, email=test_user.email)


@pytest.fixture
async def auth_client(test_token: str) -> AsyncIterator[AsyncClient]:
    """Provide an asynchronous HTTP client authenticated as test_user."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {test_token}"},
    ) as client:
        yield client


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
