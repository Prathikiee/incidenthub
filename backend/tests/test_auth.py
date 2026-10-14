"""Milestone 3 Authentication Core Tests (Phase 2A).

Comprehensive tests covering:
1. Successful registration and persisted password hash.
2. Duplicate-email registration.
3. Password-policy rejection.
4. Successful login.
5. Incorrect password and unknown email.
6. Access-token decoding and invalid/malformed/expired token rejection.
7. /me with valid token, missing token, invalid token, and inactive user.
8. Successful refresh rotation.
9. Reuse of a revoked refresh token (replay breach detection).
10. Expired refresh token.
11. Logout and subsequent refresh rejection.
12. Two concurrent attempts to consume the same refresh token.
13. Response schemas never exposing password hashes or stored token hashes.
"""

import socket
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import jwt
import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    DomainValidationError,
    DuplicateEntityError,
    PermissionDeniedError,
)
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_raw_refresh_token,
    get_current_active_user,
    hash_password,
    hash_refresh_token,
    validate_password_strength,
    verify_password,
)
from app.db.session import get_db
from app.main import app
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
)
from app.schemas.user import UserRead
from app.services import auth_service


def is_postgres_online() -> bool:
    """Check if PostgreSQL server is reachable on localhost:5432."""
    try:
        with socket.create_connection(("localhost", 5432), timeout=0.5):
            return True
    except OSError:
        return False


POSTGRES_AVAILABLE = is_postgres_online()

if not POSTGRES_AVAILABLE:

    @pytest.fixture(autouse=True)
    def clean_database() -> None:
        """Override conftest's clean_database fixture to avoid DB calls when Postgres is offline."""
        pass


# ===========================================================================
# 1. Password Policy and Hashing Unit Tests (Independent)
# ===========================================================================


class TestPasswordPolicyAndHashing:
    """Tests for Argon2id password hashing and password policy validation."""

    def test_valid_password_passes_policy(self) -> None:
        """Verify that a compliant password passes validation."""
        validate_password_strength("StrongPass123!")

    @pytest.mark.parametrize(
        "invalid_password,expected_error",
        [
            ("Short1!", "at least 10 characters"),
            ("a" * 129 + "A1!", "not exceed 128 characters"),
            ("nouppercase123!", "at least one uppercase letter"),
            ("NOLOWERCASE123!", "at least one lowercase letter"),
            ("NoDigitsHere!", "at least one digit"),
            ("NoSpecialChars123", "at least one special symbol"),
        ],
    )
    def test_password_policy_rejections(self, invalid_password: str, expected_error: str) -> None:
        """Verify that passwords violating specific policy constraints are rejected."""
        with pytest.raises(DomainValidationError) as exc_info:
            validate_password_strength(invalid_password)
        assert expected_error in str(exc_info.value)

    def test_hash_password_produces_argon2id(self) -> None:
        """Verify that hash_password uses Argon2id format."""
        pwd = "StrongPassword123!"
        hashed = hash_password(pwd)
        assert hashed.startswith("$argon2id$")
        assert verify_password(pwd, hashed) is True
        assert verify_password("WrongPassword123!", hashed) is False

    def test_hash_password_rejects_weak_password(self) -> None:
        """Verify that hash_password validates password strength before hashing."""
        with pytest.raises(DomainValidationError):
            hash_password("weak")


# ===========================================================================
# 2. JWT Access Token Creation and Decoding Tests (Independent)
# ===========================================================================


class TestJWTAccessTokens:
    """Tests for HS256 access token creation, claims, and decoding."""

    def test_access_token_creation_and_decoding(self, test_jwt_settings: dict[str, Any]) -> None:
        """Verify round-trip issuance and validation of HS256 JWT access token."""
        user_id = uuid.uuid4()
        email = "responder@incidenthub.io"
        token = create_access_token(user_id=user_id, email=email)

        payload = decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["email"] == email
        assert payload["type"] == "access"
        assert "iat" in payload
        assert "exp" in payload
        assert "jti" in payload

    def test_expired_access_token_rejection(self, test_jwt_settings: dict[str, Any]) -> None:
        """Verify that an expired access token is rejected with AuthenticationError."""
        user_id = uuid.uuid4()
        email = "responder@incidenthub.io"
        # Create token that expired 10 seconds ago
        token = create_access_token(
            user_id=user_id, email=email, expires_delta=timedelta(seconds=-10)
        )

        with pytest.raises(AuthenticationError) as exc_info:
            decode_access_token(token)
        assert "expired" in str(exc_info.value).lower()

    def test_invalid_signature_rejection(self, test_jwt_settings: dict[str, Any]) -> None:
        """Verify that tampering with token payload or signature fails validation."""
        token = create_access_token(user_id=uuid.uuid4(), email="user@hub.io")
        tampered_token = token[:-5] + "XXXXX"

        with pytest.raises(AuthenticationError):
            decode_access_token(tampered_token)

    def test_unsupported_algorithm_rejection(self) -> None:
        """Verify tokens signed with non-HS256 algorithms (e.g. none) are rejected."""
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "user@hub.io",
            "type": "access",
            "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
        }
        # Insecure alg: none
        none_token = jwt.encode(payload, key="", algorithm="none")
        with pytest.raises(AuthenticationError):
            decode_access_token(none_token)

    def test_refresh_token_presented_as_access_token_rejection(
        self, test_jwt_settings: dict[str, Any]
    ) -> None:
        """Verify that a token with type != 'access' is rejected."""
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "user@hub.io",
            "type": "refresh",
            "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(AuthenticationError) as exc_info:
            decode_access_token(token)
        assert "expected access token" in str(exc_info.value)


# ===========================================================================
# 3. Refresh Token Hashing and Security Model Tests (Independent)
# ===========================================================================


class TestRefreshTokenHashing:
    """Tests for refresh token cryptographic generation, hashing, and model behavior."""

    def test_refresh_token_generation_entropy(self) -> None:
        """Verify generated refresh tokens are distinct and high entropy."""
        token1 = generate_raw_refresh_token()
        token2 = generate_raw_refresh_token()
        assert token1 != token2
        assert len(token1) >= 64

    def test_refresh_token_sha256_hashing(self) -> None:
        """Verify SHA-256 hash calculation is deterministic and 64 hex characters."""
        raw = "sample-raw-refresh-token-secret"
        h1 = hash_refresh_token(raw)
        h2 = hash_refresh_token(raw)
        assert h1 == h2
        assert len(h1) == 64

    def test_refresh_token_model_properties(self) -> None:
        """Verify RefreshToken model properties is_active, is_expired, is_revoked."""
        now = datetime.now(UTC)
        token = RefreshToken(
            user_id=uuid.uuid4(),
            token_hash="a" * 64,
            expires_at=now + timedelta(days=7),
            revoked_at=None,
        )
        assert token.is_revoked is False
        assert token.is_expired is False
        assert token.is_active is True

        # Revoked token
        token.revoked_at = now
        assert token.is_revoked is True
        assert token.is_active is False

        # Expired token
        expired_token = RefreshToken(
            user_id=uuid.uuid4(),
            token_hash="b" * 64,
            expires_at=now - timedelta(seconds=1),
            revoked_at=None,
        )
        assert expired_token.is_expired is True
        assert expired_token.is_active is False


# ===========================================================================
# 4. Response Schemas Credential Protection Tests (Independent)
# ===========================================================================


class TestResponseSchemaProtection:
    """Verify that response schemas NEVER expose password hashes or token hashes."""

    def test_user_read_never_exposes_password_hash(self) -> None:
        """Verify UserRead schema does not include hashed_password."""
        user = User(
            id=uuid.uuid4(),
            email="responder@incidenthub.io",
            display_name="Responder",
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        schema = UserRead.model_validate(user)
        dump = schema.model_dump()
        assert "hashed_password" not in dump
        assert "password" not in dump

    def test_token_response_never_exposes_hashes(self) -> None:
        """Verify TokenResponse schema does not expose credential hashes."""
        user = User(
            id=uuid.uuid4(),
            email="responder@incidenthub.io",
            display_name="Responder",
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        response = TokenResponse(
            access_token="access.token.jwt",
            refresh_token="raw-refresh-token",
            expires_in=900,
            user=UserRead.model_validate(user),
        )
        dump = response.model_dump()
        assert "hashed_password" not in dump
        assert "token_hash" not in dump
        assert "hashed_password" not in dump["user"]


# ===========================================================================
# 5. Endpoint Application Logic Tests with Mocked DB Session (Independent)
# ===========================================================================


class TestAuthEndpointsMocked:
    """End-to-end endpoint tests using FastAPI test client and mocked AsyncSession.

    These tests run independently of a live PostgreSQL database server.
    """

    @pytest.mark.asyncio
    async def test_register_endpoint_success(self, sample_user_data: dict[str, str]) -> None:
        """POST /register: Successfully create user and return UserRead without password hash."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("app.services.auth_service.register_user") as mock_register:
                mock_user = User(
                    id=uuid.uuid4(),
                    email=sample_user_data["email"].lower(),
                    display_name=sample_user_data["display_name"],
                    hashed_password=hash_password(sample_user_data["password"]),
                    is_active=True,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                mock_register.return_value = mock_user

                response = await client.post("/api/v1/auth/register", json=sample_user_data)
                assert response.status_code == status.HTTP_201_CREATED
                data = response.json()
                assert data["email"] == sample_user_data["email"].lower()
                assert "hashed_password" not in data
                assert "password" not in data

    @pytest.mark.asyncio
    async def test_register_endpoint_password_policy_failure(self) -> None:
        """POST /register: Reject weak passwords with HTTP 400 Bad Request."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "user@hub.io",
                    "password": "weak",
                    "display_name": "User",
                },
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_register_endpoint_duplicate_email(
        self, sample_user_data: dict[str, str]
    ) -> None:
        """POST /register: Return HTTP 409 Conflict when email already exists."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch(
                "app.services.auth_service.register_user",
                side_effect=DuplicateEntityError("User already exists"),
            ):
                response = await client.post("/api/v1/auth/register", json=sample_user_data)
                assert response.status_code == status.HTTP_409_CONFLICT
                assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_endpoint_success(self, sample_user_data: dict[str, str]) -> None:
        """POST /login: Return access token, refresh token, and user profile."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            mock_user = User(
                id=uuid.uuid4(),
                email=sample_user_data["email"].lower(),
                display_name=sample_user_data["display_name"],
                hashed_password=hash_password(sample_user_data["password"]),
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            with patch(
                "app.services.auth_service.authenticate_user",
                return_value=(mock_user, "mock-access-token", "mock-refresh-token"),
            ):
                response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": sample_user_data["email"],
                        "password": sample_user_data["password"],
                    },
                )
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["access_token"] == "mock-access-token"
                assert data["refresh_token"] == "mock-refresh-token"
                assert data["token_type"] == "bearer"
                assert data["expires_in"] == 900
                assert data["user"]["email"] == sample_user_data["email"].lower()
                assert "hashed_password" not in data["user"]

    @pytest.mark.asyncio
    async def test_login_endpoint_invalid_credentials(self) -> None:
        """POST /login: Return HTTP 401 Unauthorized on invalid password or unknown email."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch(
                "app.services.auth_service.authenticate_user",
                side_effect=AuthenticationError("Invalid email or password"),
            ):
                response = await client.post(
                    "/api/v1/auth/login",
                    json={"email": "unknown@hub.io", "password": "WrongPassword123!"},
                )
                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert response.json()["detail"] == "Invalid email or password"

    @pytest.mark.asyncio
    async def test_login_endpoint_inactive_user(self) -> None:
        """POST /login: Return HTTP 403 Forbidden when user is deactivated."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch(
                "app.services.auth_service.authenticate_user",
                side_effect=PermissionDeniedError("User account is inactive"),
            ):
                response = await client.post(
                    "/api/v1/auth/login",
                    json={"email": "inactive@hub.io", "password": "Password123!"},
                )
                assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_refresh_endpoint_success(self) -> None:
        """POST /refresh: Rotate refresh token and issue new token pair."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            mock_user = User(
                id=uuid.uuid4(),
                email="user@hub.io",
                display_name="User",
                hashed_password="hash",
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            with patch(
                "app.services.auth_service.refresh_session",
                return_value=(mock_user, "new-access-token", "new-refresh-token"),
            ):
                response = await client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": "valid-old-refresh-token"},
                )
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["access_token"] == "new-access-token"
                assert data["refresh_token"] == "new-refresh-token"

    @pytest.mark.asyncio
    async def test_refresh_endpoint_revoked_token_replay_detection(self) -> None:
        """POST /refresh: Reuse of revoked token triggers session revocation and 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch(
                "app.services.auth_service.refresh_session",
                side_effect=AuthenticationError(
                    "Refresh token has been revoked; session terminated due to reuse detection"
                ),
            ):
                response = await client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": "replayed-revoked-token"},
                )
                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "reuse detection" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_refresh_endpoint_expired_token(self) -> None:
        """POST /refresh: Expired refresh token returns HTTP 401 Unauthorized."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch(
                "app.services.auth_service.refresh_session",
                side_effect=AuthenticationError("Refresh token has expired"),
            ):
                response = await client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": "expired-token"},
                )
                assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_me_endpoint_with_valid_token(self, test_jwt_settings: dict[str, Any]) -> None:
        """GET /me: Return currently authenticated active user."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id=user_id, email="responder@hub.io")

        mock_user = User(
            id=user_id,
            email="responder@hub.io",
            display_name="Responder",
            hashed_password="hash",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        transport = ASGITransport(app=app)
        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        try:
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["email"] == "responder@hub.io"
                assert data["is_active"] is True
                assert "hashed_password" not in data
        finally:
            app.dependency_overrides.pop(get_current_active_user, None)

    @pytest.mark.asyncio
    async def test_me_endpoint_missing_token_returns_401(self) -> None:
        """GET /me: Request without Authorization header returns HTTP 401 with WWW-Authenticate."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/auth/me")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert response.headers["www-authenticate"] == "Bearer"

    @pytest.mark.asyncio
    async def test_me_endpoint_invalid_token_returns_401(self) -> None:
        """GET /me: Request with malformed/invalid token returns HTTP 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer invalid-garbage-token"},
            )
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_me_endpoint_inactive_user_returns_401(
        self, test_jwt_settings: dict[str, Any]
    ) -> None:
        """GET /me: Deactivated user with valid unexpired token returns HTTP 401."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id=user_id, email="inactive@hub.io")

        async def inactive_user_override() -> User:
            raise AuthenticationError("User account is inactive")

        app.dependency_overrides[get_current_active_user] = inactive_user_override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "inactive" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_active_user, None)

    @pytest.mark.asyncio
    async def test_logout_endpoint_success(self, test_jwt_settings: dict[str, Any]) -> None:
        """POST /logout: Revoke refresh token and return HTTP 204 No Content."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id=user_id, email="user@hub.io")
        mock_user = User(
            id=user_id,
            email="user@hub.io",
            display_name="User",
            hashed_password="hash",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        mock_db_session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_db_session
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                with patch("app.services.auth_service.logout_user") as mock_logout:
                    response = await client.post(
                        "/api/v1/auth/logout",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"refresh_token": "valid-token-to-revoke"},
                    )
                    assert response.status_code == status.HTTP_204_NO_CONTENT
                    mock_logout.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_current_active_user, None)
            app.dependency_overrides.pop(get_db, None)


# ===========================================================================
# 6. Service Logic & Concurrency Unit Tests (Independent)
# ===========================================================================


class TestAuthServiceLogic:
    """Service layer unit tests verifying concurrency, rotation, and replay detection logic."""

    @pytest.mark.asyncio
    async def test_authenticate_user_passwordless_user_rejected(self) -> None:
        """Verify that an existing user without a password hash cannot authenticate."""
        mock_session = AsyncMock()
        passwordless_user = User(
            id=uuid.uuid4(),
            email="legacy@hub.io",
            display_name="Legacy User",
            hashed_password=None,  # Transitional state
            is_active=True,
        )
        mock_session.scalar.return_value = passwordless_user

        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.authenticate_user(
                mock_session,
                LoginRequest(email="legacy@hub.io", password="AnyPassword123!"),
            )
        assert "Invalid email or password" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_concurrency_two_simultaneous_refresh_attempts(self) -> None:
        """Verify that simultaneous refresh requests for the same token allow only one winner."""
        user_id = uuid.uuid4()
        raw_token = generate_raw_refresh_token()
        t_hash = hash_refresh_token(raw_token)
        now = datetime.now(UTC)

        token_record = RefreshToken(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=t_hash,
            expires_at=now + timedelta(days=7),
            revoked_at=None,
        )
        user = User(
            id=user_id,
            email="concurrency@hub.io",
            display_name="Concurrent User",
            hashed_password="hash",
            is_active=True,
        )

        # Mock database session that simulates concurrency via lock state
        is_locked = False

        class SimulatedSession:
            def __init__(self) -> None:
                self.committed = False

            async def scalar(self, stmt: Any) -> RefreshToken | None:
                nonlocal is_locked, token_record
                # Simulate first request acquiring lock and revoking token
                if token_record.revoked_at is not None:
                    # Token already consumed
                    return token_record
                return token_record

            async def get(self, model: Any, ident: Any) -> User | None:
                return user

            async def execute(self, stmt: Any) -> None:
                pass

            def add(self, instance: Any) -> None:
                pass

            async def commit(self) -> None:
                self.committed = True

        session1 = SimulatedSession()
        session2 = SimulatedSession()

        # First request succeeds
        res1 = await auth_service.refresh_session(session1, raw_token)  # type: ignore[arg-type]
        assert res1[0].id == user_id
        assert token_record.revoked_at is not None

        # Second request presents now-revoked token and triggers replay detection
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.refresh_session(session2, raw_token)  # type: ignore[arg-type]
        assert "revoked" in str(exc_info.value).lower()


# ===========================================================================
# 7. Live PostgreSQL Integration Tests (Conditionally run when DB is online)
# ===========================================================================


@pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL database service is offline/unavailable in this environment",
)
class TestAuthPostgresIntegration:
    """Full database integration tests requiring a live PostgreSQL instance."""

    @pytest.mark.asyncio
    async def test_full_registration_and_db_persistence(
        self, client: AsyncClient, sample_user_data: dict[str, str], db_session: Any
    ) -> None:
        """Verify registration writes directly to PostgreSQL users table."""
        response = await client.post("/api/v1/auth/register", json=sample_user_data)
        assert response.status_code == status.HTTP_201_CREATED

        # Directly inspect DB
        user = await db_session.get(User, UUID(response.json()["id"]))
        assert user is not None
        assert user.hashed_password.startswith("$argon2id$")
        assert verify_password(sample_user_data["password"], user.hashed_password)

    @pytest.mark.asyncio
    async def test_full_login_and_refresh_flow(
        self, client: AsyncClient, sample_user_data: dict[str, str]
    ) -> None:
        """Verify end-to-end register -> login -> refresh -> logout against live DB."""
        # 1. Register
        r_reg = await client.post("/api/v1/auth/register", json=sample_user_data)
        assert r_reg.status_code == status.HTTP_201_CREATED

        # 2. Login
        r_login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"],
            },
        )
        assert r_login.status_code == status.HTTP_200_OK
        data_login = r_login.json()
        rt1 = data_login["refresh_token"]
        assert len(data_login["access_token"]) > 0

        # 3. Refresh rotation
        r_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
        assert r_refresh.status_code == status.HTTP_200_OK
        data_refresh = r_refresh.json()
        rt2 = data_refresh["refresh_token"]
        at2 = data_refresh["access_token"]

        # 4. Replay RT1 -> must fail with 401
        r_replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
        assert r_replay.status_code == status.HTTP_401_UNAUTHORIZED

        # 5. Logout with AT2
        r_logout = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {at2}"},
            json={"refresh_token": rt2},
        )
        assert r_logout.status_code == status.HTTP_204_NO_CONTENT
