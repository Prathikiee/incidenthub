"""User API endpoints with authentication and tenant scoping."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundError
from app.core.security import get_current_active_user
from app.db.session import get_db
from app.models.membership import OrganizationMembership
from app.models.user import User
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
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserRead]:
    """List users scoped to organizations shared with the authenticated user.

    Never exposes an unauthenticated global user directory or credentials/hashes.
    """
    stmt = (
        select(User)
        .where(
            (User.id == current_user.id)
            | User.id.in_(
                select(OrganizationMembership.user_id).where(
                    OrganizationMembership.organization_id.in_(
                        select(OrganizationMembership.organization_id).where(
                            OrganizationMembership.user_id == current_user.id
                        )
                    )
                )
            )
        )
        .distinct()
        .offset(skip)
        .limit(limit)
        .order_by(User.created_at.desc())
    )
    result = await db.scalars(stmt)
    return [UserRead.model_validate(u) for u in result.all()]


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get User",
)
async def get_user_endpoint(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Retrieve user details by ID for the current user or a colleague in shared organizations."""
    if user_id == current_user.id:
        return UserRead.model_validate(current_user)

    # Check shared organization membership to prevent cross-tenant user lookup
    shares_org = await db.scalar(
        select(OrganizationMembership.id)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id.in_(
                select(OrganizationMembership.organization_id).where(
                    OrganizationMembership.user_id == current_user.id
                )
            ),
        )
        .limit(1)
    )
    if not shares_org:
        raise EntityNotFoundError(f"User '{user_id}' not found")

    user = await user_service.get_user(db, user_id)
    return UserRead.model_validate(user)
