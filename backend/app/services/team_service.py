"""Team service layer operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateEntityError, EntityNotFoundError
from app.models.organization import Organization
from app.models.team import Team
from app.schemas.team import TeamCreate


async def create_team(
    db: AsyncSession,
    organization_id: UUID,
    data: TeamCreate,
) -> Team:
    """Create a new team within an organization ensuring unique name per organization."""
    org = await db.get(Organization, organization_id)
    if not org:
        raise EntityNotFoundError(f"Organization '{organization_id}' not found")

    existing = await db.scalar(
        select(Team).where(
            Team.organization_id == organization_id,
            Team.name == data.name,
        )
    )
    if existing:
        raise DuplicateEntityError(
            f"Team with name '{data.name}' already exists in organization '{organization_id}'"
        )

    team = Team(
        organization_id=organization_id,
        name=data.name,
        description=data.description,
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


async def get_team(
    db: AsyncSession,
    organization_id: UUID,
    team_id: UUID,
) -> Team:
    """Retrieve a team by ID scoped to its organization."""
    team = await db.get(Team, team_id)
    if not team or team.organization_id != organization_id:
        raise EntityNotFoundError(f"Team '{team_id}' not found in organization '{organization_id}'")
    return team


async def list_teams(
    db: AsyncSession,
    organization_id: UUID,
) -> list[Team]:
    """List all teams belonging to an organization."""
    org = await db.get(Organization, organization_id)
    if not org:
        raise EntityNotFoundError(f"Organization '{organization_id}' not found")

    result = await db.scalars(
        select(Team).where(Team.organization_id == organization_id).order_by(Team.created_at.asc())
    )
    return list(result.all())
