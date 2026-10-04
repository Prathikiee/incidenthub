"""User service layer operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateEntityError, EntityNotFoundError
from app.models.user import User
from app.schemas.user import UserCreate


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """Create a new user with normalized email address."""
    normalized_email = data.email.strip().lower()
    existing = await db.scalar(select(User).where(User.email == normalized_email))
    if existing:
        raise DuplicateEntityError(f"User with email '{normalized_email}' already exists")

    user = User(
        email=normalized_email,
        display_name=data.display_name,
        is_active=data.is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user(db: AsyncSession, user_id: UUID) -> User:
    """Retrieve a user by their ID or raise EntityNotFoundError."""
    user = await db.get(User, user_id)
    if not user:
        raise EntityNotFoundError(f"User '{user_id}' not found")
    return user


async def list_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
) -> list[User]:
    """List users ordered by creation date."""
    result = await db.scalars(
        select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
    )
    return list(result.all())
