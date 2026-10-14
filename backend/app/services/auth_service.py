"""Authentication and session management business logic service layer."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    DuplicateEntityError,
    PermissionDeniedError,
)
from app.core.security import (
    create_access_token,
    generate_raw_refresh_token,
    hash_password,
    hash_refresh_token,
    validate_password_strength,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    """Register a new platform user with normalized email and Argon2id hashed password.

    Does NOT create default organizations or memberships.
    """
    normalized_email = data.email.strip().lower()

    # Enforce password policy constraints
    validate_password_strength(data.password)

    # Check email uniqueness
    existing = await db.scalar(select(User).where(User.email == normalized_email))
    if existing:
        raise DuplicateEntityError(f"User with email '{normalized_email}' already exists")

    # Securely hash password using pwdlib Argon2id
    hashed = hash_password(data.password)

    user = User(
        email=normalized_email,
        display_name=data.display_name.strip(),
        hashed_password=hashed,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession,
    data: LoginRequest,
    user_agent: str | None = None,
) -> tuple[User, str, str]:
    """Verify user credentials and issue an access token and refresh token pair."""
    normalized_email = data.email.strip().lower()

    user = await db.scalar(select(User).where(User.email == normalized_email))
    if not user or not user.hashed_password:
        raise AuthenticationError("Invalid email or password")

    if not verify_password(data.password, user.hashed_password):
        raise AuthenticationError("Invalid email or password")

    if not user.is_active:
        raise PermissionDeniedError("User account is inactive")

    # Issue short-lived stateless JWT access token
    access_token = create_access_token(user_id=user.id, email=user.email)

    # Issue and persist cryptographically secure refresh token
    raw_refresh = generate_raw_refresh_token()
    token_hash = hash_refresh_token(raw_refresh)
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
    )
    db.add(refresh_record)
    await db.commit()

    return user, access_token, raw_refresh


async def refresh_session(
    db: AsyncSession,
    raw_refresh_token: str,
    user_agent: str | None = None,
) -> tuple[User, str, str]:
    """Validate and rotate a refresh token with concurrency locking and breach/replay detection."""
    token_hash = hash_refresh_token(raw_refresh_token)

    # Row-level locking to ensure atomic, concurrency-safe rotation
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    token_record = await db.scalar(stmt)

    if not token_record:
        raise AuthenticationError("Invalid or expired refresh token")

    now = datetime.now(UTC)

    # Replay detection: if a revoked refresh token is presented, revoke all active sessions for that user
    if token_record.revoked_at is not None:
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == token_record.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await db.commit()
        raise AuthenticationError(
            "Refresh token has been revoked; session terminated due to reuse detection"
        )

    # Check expiration
    exp = token_record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if exp <= now:
        token_record.revoked_at = now
        await db.commit()
        raise AuthenticationError("Refresh token has expired")

    # Verify user existence and active status
    user = await db.get(User, token_record.user_id)
    if not user or not user.is_active:
        token_record.revoked_at = now
        await db.commit()
        raise AuthenticationError("User account is inactive or not found")

    # Atomically consume old token and issue replacement
    token_record.revoked_at = now

    new_raw_refresh = generate_raw_refresh_token()
    new_token_hash = hash_refresh_token(new_raw_refresh)
    new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    new_record = RefreshToken(
        user_id=user.id,
        token_hash=new_token_hash,
        expires_at=new_expires_at,
        user_agent=user_agent or token_record.user_agent,
    )
    db.add(new_record)
    await db.commit()

    new_access_token = create_access_token(user_id=user.id, email=user.email)
    return user, new_access_token, new_raw_refresh


async def logout_user(
    db: AsyncSession,
    raw_refresh_token: str,
    current_user: User,
) -> None:
    """Revoke a refresh token idempotently for the currently authenticated user."""
    token_hash = hash_refresh_token(raw_refresh_token)

    stmt = (
        select(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == current_user.id,
        )
        .with_for_update()
    )
    token_record = await db.scalar(stmt)
    if token_record and token_record.revoked_at is None:
        token_record.revoked_at = datetime.now(UTC)
        await db.commit()
