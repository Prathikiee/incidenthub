"""Unit tests for Milestone 3 Security Foundation: configuration, exceptions, and handlers."""

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    DomainException,
    DomainValidationError,
    DuplicateEntityError,
    EntityNotFoundError,
    PermissionDeniedError,
    TenantContextMissingError,
)
from app.main import app


@pytest.fixture(autouse=True)
def clean_database() -> None:
    """Override conftest's clean_database fixture to avoid DB calls in non-DB unit tests."""
    pass


# ---------------------------------------------------------------------------
# Configuration Tests
# ---------------------------------------------------------------------------


def test_jwt_configuration_defaults() -> None:
    """Verify default security configuration values adhere to Milestone 3 specifications."""
    cfg = Settings(ENVIRONMENT="development")
    assert cfg.JWT_ALGORITHM == "HS256"
    assert cfg.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert cfg.REFRESH_TOKEN_EXPIRE_DAYS == 7
    assert len(cfg.JWT_SECRET_KEY) >= 32
    assert "dev-insecure" in cfg.JWT_SECRET_KEY


def test_jwt_secret_key_minimum_length_in_non_test_environment() -> None:
    """Verify that secrets with fewer than 32 characters are rejected in non-test environments."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="development",
            JWT_SECRET_KEY="short-secret-under-32-chars",
        )
    assert "at least 32 characters" in str(exc_info.value)


def test_jwt_secret_key_production_insecure_default_rejection() -> None:
    """Verify that insecure development default secrets are strictly rejected in production."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="dev-insecure-secret-key-change-in-production-min32chars",
        )
    assert "must not use development default values" in str(exc_info.value)


def test_jwt_secret_key_production_valid_secret() -> None:
    """Verify that a sufficiently strong secret is accepted in production."""
    strong_secret = "a" * 32
    cfg = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY=strong_secret,
    )
    assert cfg.JWT_SECRET_KEY == strong_secret
    assert cfg.ENVIRONMENT == "production"


def test_jwt_secret_key_allowed_in_test_environment() -> None:
    """Verify that test environments allow short or mock secrets for testing convenience."""
    cfg = Settings(
        ENVIRONMENT="test",
        JWT_SECRET_KEY="short-test-secret",
    )
    assert cfg.JWT_SECRET_KEY == "short-test-secret"


def test_jwt_algorithm_restricted_to_hs256() -> None:
    """Verify that algorithms other than HS256 are rejected by Pydantic validation."""
    with pytest.raises(ValidationError):
        Settings.model_validate({"JWT_ALGORITHM": "none"})

    with pytest.raises(ValidationError):
        Settings.model_validate({"JWT_ALGORITHM": "RS256"})


def test_jwt_token_lifetimes_must_be_positive() -> None:
    """Verify that zero or negative token expiration lifetimes are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(ACCESS_TOKEN_EXPIRE_MINUTES=0)
    assert "ACCESS_TOKEN_EXPIRE_MINUTES must be greater than 0" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        Settings(REFRESH_TOKEN_EXPIRE_DAYS=-1)
    assert "REFRESH_TOKEN_EXPIRE_DAYS must be greater than 0" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Exceptions & Handlers Tests
# ---------------------------------------------------------------------------


def test_exception_inheritance() -> None:
    """Verify that all security exceptions inherit from DomainException."""
    auth_err = AuthenticationError()
    perm_err = PermissionDeniedError()
    ctx_err = TenantContextMissingError()

    assert isinstance(auth_err, DomainException)
    assert isinstance(perm_err, DomainException)
    assert isinstance(ctx_err, DomainException)


def test_authentication_error_default_and_custom() -> None:
    """Verify default and customized attributes on AuthenticationError."""
    default_err = AuthenticationError()
    assert default_err.message == "Could not validate credentials"
    assert default_err.headers == {"WWW-Authenticate": "Bearer"}

    custom_headers = {"WWW-Authenticate": 'Bearer error="invalid_token"'}
    custom_err = AuthenticationError("Token expired", headers=custom_headers)
    assert custom_err.message == "Token expired"
    assert custom_err.headers == custom_headers


def test_permission_denied_error_message() -> None:
    """Verify PermissionDeniedError message handling."""
    err = PermissionDeniedError("Admin role required")
    assert err.message == "Admin role required"


def test_tenant_context_missing_error_message() -> None:
    """Verify TenantContextMissingError message handling."""
    err = TenantContextMissingError("Organization ID missing in path")
    assert err.message == "Organization ID missing in path"


# ---------------------------------------------------------------------------
# FastAPI Exception Handler Integration Tests
# ---------------------------------------------------------------------------

exception_test_router = APIRouter(prefix="/api/v1/test-exceptions")


@exception_test_router.get("/auth-error")
async def route_auth_error() -> None:
    raise AuthenticationError("Invalid access token signature")


@exception_test_router.get("/perm-error")
async def route_perm_error() -> None:
    raise PermissionDeniedError("Insufficient role permissions")


@exception_test_router.get("/tenant-error")
async def route_tenant_error() -> None:
    raise TenantContextMissingError("Tenant context is required")


@exception_test_router.get("/entity-not-found")
async def route_not_found() -> None:
    raise EntityNotFoundError("Entity not found")


@exception_test_router.get("/duplicate-entity")
async def route_duplicate() -> None:
    raise DuplicateEntityError("Entity already exists")


@exception_test_router.get("/domain-validation")
async def route_validation() -> None:
    raise DomainValidationError("Invalid domain rule")


app.include_router(exception_test_router)


@pytest.mark.asyncio
async def test_authentication_exception_handler() -> None:
    """Verify AuthenticationError is handled with 401 and WWW-Authenticate header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        response = await test_client.get("/api/v1/test-exceptions/auth-error")
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid access token signature"}
        assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_permission_denied_exception_handler() -> None:
    """Verify PermissionDeniedError is handled with 403 Forbidden."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        response = await test_client.get("/api/v1/test-exceptions/perm-error")
        assert response.status_code == 403
        assert response.json() == {"detail": "Insufficient role permissions"}


@pytest.mark.asyncio
async def test_tenant_context_missing_exception_handler() -> None:
    """Verify TenantContextMissingError is handled with 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        response = await test_client.get("/api/v1/test-exceptions/tenant-error")
        assert response.status_code == 400
        assert response.json() == {"detail": "Tenant context is required"}


@pytest.mark.asyncio
async def test_existing_domain_exception_handlers_preserved() -> None:
    """Verify that existing exception handlers (404, 409, 400) continue to operate correctly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        r404 = await test_client.get("/api/v1/test-exceptions/entity-not-found")
        assert r404.status_code == 404
        assert r404.json() == {"detail": "Entity not found"}

        r409 = await test_client.get("/api/v1/test-exceptions/duplicate-entity")
        assert r409.status_code == 409
        assert r409.json() == {"detail": "Entity already exists"}

        r400 = await test_client.get("/api/v1/test-exceptions/domain-validation")
        assert r400.status_code == 400
        assert r400.json() == {"detail": "Invalid domain rule"}


# ---------------------------------------------------------------------------
# Test Fixtures Verification Tests
# ---------------------------------------------------------------------------


def test_auth_headers_fixture(auth_headers: pytest.FixtureRequest) -> None:
    """Verify the auth_headers fixture from conftest.py generates correct bearer headers."""
    # auth_headers is a callable fixture
    headers = auth_headers("test-token-value")  # type: ignore[operator]
    assert headers == {"Authorization": "Bearer test-token-value"}


def test_sample_user_data_fixture(sample_user_data: dict[str, str]) -> None:
    """Verify the sample_user_data fixture from conftest.py matches requirements."""
    assert "email" in sample_user_data
    assert "password" in sample_user_data
    assert "display_name" in sample_user_data
    assert len(sample_user_data["password"]) >= 10


def test_test_jwt_settings_fixture(test_jwt_settings: dict[str, str | int]) -> None:
    """Verify the test_jwt_settings fixture configures settings appropriately."""
    assert test_jwt_settings["JWT_ALGORITHM"] == "HS256"
    assert test_jwt_settings["ACCESS_TOKEN_EXPIRE_MINUTES"] == 15
    assert test_jwt_settings["REFRESH_TOKEN_EXPIRE_DAYS"] == 7
    assert len(str(test_jwt_settings["JWT_SECRET_KEY"])) >= 32
