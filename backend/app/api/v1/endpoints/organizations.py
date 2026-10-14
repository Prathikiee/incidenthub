"""Organization API endpoints with multi-tenant authorization guards."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import (
    OrganizationContext,
    get_organization_context,
    require_admin,
)
from app.core.security import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.membership import (
    OrganizationMembershipCreate,
    OrganizationMembershipRead,
    OrganizationMembershipUpdate,
)
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationRead,
)
from app.services import membership_service, organization_service

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post(
    "",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Organization",
)
async def create_organization_endpoint(
    data: OrganizationCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationRead:
    """Create a new organization with a unique slug and automatically assign creator as OWNER."""
    org = await organization_service.create_organization(db, data, creator=current_user)
    return OrganizationRead.model_validate(org)


@router.get(
    "",
    response_model=list[OrganizationRead],
    summary="List Organizations",
)
async def list_organizations_endpoint(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationRead]:
    """List organizations for which the authenticated user holds an active membership."""
    orgs = await organization_service.list_user_organizations(
        db, user_id=current_user.id, skip=skip, limit=limit
    )
    return [OrganizationRead.model_validate(o) for o in orgs]


@router.get(
    "/{organization_id}",
    response_model=OrganizationRead,
    summary="Get Organization",
)
async def get_organization_endpoint(
    ctx: OrganizationContext = Depends(get_organization_context),
) -> OrganizationRead:
    """Retrieve organization details. Rejects non-members with 404 to prevent enumeration."""
    return OrganizationRead.model_validate(ctx.organization)


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMembershipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add Organization Member",
)
async def add_organization_member_endpoint(
    data: OrganizationMembershipCreate,
    ctx: OrganizationContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMembershipRead:
    """Add a user as a member to an organization.

    Requires ADMIN or OWNER role. Only OWNER may assign ADMIN or OWNER roles.
    Rejects self-assignment or self-elevation attempts.
    """
    membership = await membership_service.add_organization_member(
        db,
        organization_id=ctx.organization.id,
        data=data,
        current_user=ctx.user,
        caller_role=ctx.role,
    )
    return OrganizationMembershipRead.model_validate(membership)


@router.get(
    "/{organization_id}/members",
    response_model=list[OrganizationMembershipRead],
    summary="List Organization Members",
)
async def list_organization_members_endpoint(
    ctx: OrganizationContext = Depends(get_organization_context),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationMembershipRead]:
    """List all members of an organization. Accessible to any active member."""
    members = await membership_service.list_organization_members(
        db, organization_id=ctx.organization.id
    )
    return [OrganizationMembershipRead.model_validate(m) for m in members]


@router.patch(
    "/{organization_id}/members/{user_id}",
    response_model=OrganizationMembershipRead,
    summary="Update Organization Member Role",
)
async def update_organization_member_role_endpoint(
    user_id: UUID,
    data: OrganizationMembershipUpdate,
    ctx: OrganizationContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMembershipRead:
    """Update an organization member's role with single-owner safeguards and hierarchy checks."""
    membership = await membership_service.update_organization_member_role(
        db,
        organization_id=ctx.organization.id,
        target_user_id=user_id,
        new_role=data.role,
        current_user=ctx.user,
        caller_role=ctx.role,
    )
    return OrganizationMembershipRead.model_validate(membership)


@router.delete(
    "/{organization_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove Organization Member",
)
async def remove_organization_member_endpoint(
    user_id: UUID,
    ctx: OrganizationContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a member from an organization. Last-owner removal is rejected."""
    await membership_service.remove_organization_member(
        db,
        organization_id=ctx.organization.id,
        target_user_id=user_id,
        current_user=ctx.user,
        caller_role=ctx.role,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
