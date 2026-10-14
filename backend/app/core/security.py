"""Security utilities for password hashing, JWT operations, and auth dependencies."""

import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, DomainValidationError
from app.db.session import get_db
from app.models.user import User

# Argon2id password hasher configuration via pwdlib
password_hasher = PasswordHash((Argon2Hasher(),))

# OAuth2 password bearer scheme for extracting Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)

# Password policy constraints
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128


def validate_password_strength(password: str) -> None:
    """Validate password against complexity policy.

    Requirements:
    - Minimum 10 characters, maximum 128 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special symbol
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        raise DomainValidationError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters in length"
        )
    if len(password) > PASSWORD_MAX_LENGTH:
        raise DomainValidationError(
            f"Password must not exceed {PASSWORD_MAX_LENGTH} characters in length"
        )
    if not re.search(r"[A-Z]", password):
        raise DomainValidationError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise DomainValidationError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise DomainValidationError("Password must contain at least one digit")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise DomainValidationError("Password must contain at least one special symbol")


def hash_password(password: str) -> str:
    """Hash a password using Argon2id after validating policy constraints."""
    validate_password_strength(password)
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against an Argon2id hash."""
    return password_hasher.verify(plain_password, hashed_password)


def create_access_token(
    user_id: UUID | str,
    email: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed HS256 JWT access token with identity and temporal claims."""
    now = datetime.now(UTC)
    expiry = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expiry.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type; expected access token")
        if not payload.get("sub"):
            raise AuthenticationError("Token missing subject claim")
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Access token has expired") from None
    except jwt.InvalidTokenError as err:
        raise AuthenticationError(f"Invalid access token: {err}") from None
    except AuthenticationError:
        raise
    except Exception as err:
        raise AuthenticationError(f"Could not validate credentials: {err}") from None


def generate_raw_refresh_token() -> str:
    """Generate a high-entropy, cryptographically random raw refresh token string."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(raw_token: str) -> str:
    """Compute the SHA-256 hexadecimal digest of a raw refresh token for safe storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def get_current_user_token_payload(
    token: str | None = Depends(oauth2_scheme),
) -> dict[str, Any]:
    """FastAPI dependency to extract and decode access token claims from Authorization header."""
    if not token:
        raise AuthenticationError("Not authenticated")
    return decode_access_token(token)


async def get_current_active_user(
    token_payload: dict[str, Any] = Depends(get_current_user_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency to resolve and verify active user status from the database.

    Enforces that the user exists and is_active is True on every authenticated request.
    """
    sub = token_payload.get("sub")
    if not sub:
        raise AuthenticationError("Token missing subject identifier")

    try:
        user_id = UUID(str(sub))
    except ValueError:
        raise AuthenticationError("Invalid subject UUID in token") from None

    user = await db.get(User, user_id)
    if not user:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    return user
