"""Team API endpoints with organization authorization guards."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import (
    OrganizationContext,
    get_organization_context,
    require_admin,
)
from app.db.session import get_db
from app.schemas.membership import TeamMembershipCreate, TeamMembershipRead
from app.schemas.team import TeamCreate, TeamRead
from app.services import membership_service, team_service

router = APIRouter(prefix="/organizations/{organization_id}/teams", tags=["teams"])


@router.post(
    "",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Team",
)
async def create_team_endpoint(
    data: TeamCreate,
    ctx: OrganizationContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TeamRead:
    """Create a new team within an organization. Requires ADMIN or OWNER role."""
    team = await team_service.create_team(db, ctx.organization.id, data)
    return TeamRead.model_validate(team)


@router.get(
    "",
    response_model=list[TeamRead],
    summary="List Teams",
)
async def list_teams_endpoint(
    ctx: OrganizationContext = Depends(get_organization_context),
    db: AsyncSession = Depends(get_db),
) -> list[TeamRead]:
    """List all teams belonging to an organization. Accessible to any active member."""
    teams = await team_service.list_teams(db, ctx.organization.id)
    return [TeamRead.model_validate(t) for t in teams]


@router.get(
    "/{team_id}",
    response_model=TeamRead,
    summary="Get Team",
)
async def get_team_endpoint(
    team_id: UUID,
    ctx: OrganizationContext = Depends(get_organization_context),
    db: AsyncSession = Depends(get_db),
) -> TeamRead:
    """Retrieve team details scoped to an organization. Rejects cross-tenant access."""
    team = await team_service.get_team(db, ctx.organization.id, team_id)
    return TeamRead.model_validate(team)


@router.post(
    "/{team_id}/members",
    response_model=TeamMembershipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add Team Member",
)
async def add_team_member_endpoint(
    team_id: UUID,
    data: TeamMembershipCreate,
    ctx: OrganizationContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TeamMembershipRead:
    """Assign an organization member to a team. Requires ADMIN or OWNER role."""
    membership = await membership_service.add_team_member(db, ctx.organization.id, team_id, data)
    return TeamMembershipRead.model_validate(membership)


@router.get(
    "/{team_id}/members",
    response_model=list[TeamMembershipRead],
    summary="List Team Members",
)
async def list_team_members_endpoint(
    team_id: UUID,
    ctx: OrganizationContext = Depends(get_organization_context),
    db: AsyncSession = Depends(get_db),
) -> list[TeamMembershipRead]:
    """List all members assigned to a team. Accessible to any active member."""
    members = await membership_service.list_team_members(db, ctx.organization.id, team_id)
    return [TeamMembershipRead.model_validate(m) for m in members]
