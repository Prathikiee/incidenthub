"""User API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.user import UserCreate, UserRead
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create User",
)
async def create_user_endpoint(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Create a new user with a unique email address."""
    user = await user_service.create_user(db, data)
    return UserRead.model_validate(user)


@router.get(
    "",
    response_model=list[UserRead],
    summary="List Users",
)
async def list_users_endpoint(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[UserRead]:
    """List registered users."""
    users = await user_service.list_users(db, skip=skip, limit=limit)
    return [UserRead.model_validate(u) for u in users]


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get User",
)
async def get_user_endpoint(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Retrieve user details by ID."""
    user = await user_service.get_user(db, user_id)
    return UserRead.model_validate(user)
