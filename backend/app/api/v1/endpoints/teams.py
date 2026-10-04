"""Team API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

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
    organization_id: UUID,
    data: TeamCreate,
    db: AsyncSession = Depends(get_db),
) -> TeamRead:
    """Create a new team within an organization."""
    team = await team_service.create_team(db, organization_id, data)
    return TeamRead.model_validate(team)


@router.get(
    "",
    response_model=list[TeamRead],
    summary="List Teams",
)
async def list_teams_endpoint(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[TeamRead]:
    """List all teams belonging to an organization."""
    teams = await team_service.list_teams(db, organization_id)
    return [TeamRead.model_validate(t) for t in teams]


@router.get(
    "/{team_id}",
    response_model=TeamRead,
    summary="Get Team",
)
async def get_team_endpoint(
    organization_id: UUID,
    team_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TeamRead:
    """Retrieve team details scoped to an organization."""
    team = await team_service.get_team(db, organization_id, team_id)
    return TeamRead.model_validate(team)


@router.post(
    "/{team_id}/members",
    response_model=TeamMembershipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add Team Member",
)
async def add_team_member_endpoint(
    organization_id: UUID,
    team_id: UUID,
    data: TeamMembershipCreate,
    db: AsyncSession = Depends(get_db),
) -> TeamMembershipRead:
    """Assign an organization member to a team."""
    membership = await membership_service.add_team_member(db, organization_id, team_id, data)
    return TeamMembershipRead.model_validate(membership)


@router.get(
    "/{team_id}/members",
    response_model=list[TeamMembershipRead],
    summary="List Team Members",
)
async def list_team_members_endpoint(
    organization_id: UUID,
    team_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[TeamMembershipRead]:
    """List all members assigned to a team."""
    members = await membership_service.list_team_members(db, organization_id, team_id)
    return [TeamMembershipRead.model_validate(m) for m in members]
