"""Organization API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.membership import (
    OrganizationMembershipCreate,
    OrganizationMembershipRead,
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
    db: AsyncSession = Depends(get_db),
) -> OrganizationRead:
    """Create a new organization with a unique slug."""
    org = await organization_service.create_organization(db, data)
    return OrganizationRead.model_validate(org)


@router.get(
    "",
    response_model=list[OrganizationRead],
    summary="List Organizations",
)
async def list_organizations_endpoint(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationRead]:
    """List registered organizations."""
    orgs = await organization_service.list_organizations(db, skip=skip, limit=limit)
    return [OrganizationRead.model_validate(o) for o in orgs]


@router.get(
    "/{organization_id}",
    response_model=OrganizationRead,
    summary="Get Organization",
)
async def get_organization_endpoint(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> OrganizationRead:
    """Retrieve an organization by its ID."""
    org = await organization_service.get_organization(db, organization_id)
    return OrganizationRead.model_validate(org)


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMembershipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add Organization Member",
)
async def add_organization_member_endpoint(
    organization_id: UUID,
    data: OrganizationMembershipCreate,
    db: AsyncSession = Depends(get_db),
) -> OrganizationMembershipRead:
    """Add a user as a member to an organization."""
    membership = await membership_service.add_organization_member(db, organization_id, data)
    return OrganizationMembershipRead.model_validate(membership)


@router.get(
    "/{organization_id}/members",
    response_model=list[OrganizationMembershipRead],
    summary="List Organization Members",
)
async def list_organization_members_endpoint(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationMembershipRead]:
    """List all members of an organization."""
    members = await membership_service.list_organization_members(db, organization_id)
    return [OrganizationMembershipRead.model_validate(m) for m in members]
