"""Membership service layer operations for Organizations and Teams."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DomainValidationError,
    DuplicateEntityError,
    EntityNotFoundError,
)
from app.models.membership import OrganizationMembership, TeamMembership
from app.models.organization import Organization
from app.models.team import Team
from app.models.user import User
from app.schemas.membership import OrganizationMembershipCreate, TeamMembershipCreate


async def add_organization_member(
    db: AsyncSession,
    organization_id: UUID,
    data: OrganizationMembershipCreate,
) -> OrganizationMembership:
    """Add a user to an organization with a specified role."""
    org = await db.get(Organization, organization_id)
    if not org:
        raise EntityNotFoundError(f"Organization '{organization_id}' not found")

    user = await db.get(User, data.user_id)
    if not user:
        raise EntityNotFoundError(f"User '{data.user_id}' not found")

    existing = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == data.user_id,
        )
    )
    if existing:
        raise DuplicateEntityError(
            f"User '{data.user_id}' is already a member of organization '{organization_id}'"
        )

    membership = OrganizationMembership(
        organization_id=organization_id,
        user_id=data.user_id,
        role=data.role,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


async def list_organization_members(
    db: AsyncSession,
    organization_id: UUID,
) -> list[OrganizationMembership]:
    """List all members of an organization."""
    org = await db.get(Organization, organization_id)
    if not org:
        raise EntityNotFoundError(f"Organization '{organization_id}' not found")

    result = await db.scalars(
        select(OrganizationMembership)
        .where(OrganizationMembership.organization_id == organization_id)
        .order_by(OrganizationMembership.created_at.asc())
    )
    return list(result.all())


async def add_team_member(
    db: AsyncSession,
    organization_id: UUID,
    team_id: UUID,
    data: TeamMembershipCreate,
) -> TeamMembership:
    """Add a user to a team within an organization.

    Enforces that:
    1. Team exists and belongs to the given organization.
    2. User exists.
    3. User is an active member of the parent organization.
    4. User is not already a member of the team.
    """
    team = await db.get(Team, team_id)
    if not team or team.organization_id != organization_id:
        raise EntityNotFoundError(f"Team '{team_id}' not found in organization '{organization_id}'")

    user = await db.get(User, data.user_id)
    if not user:
        raise EntityNotFoundError(f"User '{data.user_id}' not found")

    # Verify user belongs to the parent organization
    org_membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == data.user_id,
        )
    )
    if not org_membership:
        raise DomainValidationError(
            f"User '{data.user_id}' must be an organization member before joining a team"
        )

    # Check for duplicate team membership
    existing = await db.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == data.user_id,
        )
    )
    if existing:
        raise DuplicateEntityError(f"User '{data.user_id}' is already a member of team '{team_id}'")

    membership = TeamMembership(
        team_id=team_id,
        user_id=data.user_id,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


async def list_team_members(
    db: AsyncSession,
    organization_id: UUID,
    team_id: UUID,
) -> list[TeamMembership]:
    """List all members of a team in an organization."""
    team = await db.get(Team, team_id)
    if not team or team.organization_id != organization_id:
        raise EntityNotFoundError(f"Team '{team_id}' not found in organization '{organization_id}'")

    result = await db.scalars(
        select(TeamMembership)
        .where(TeamMembership.team_id == team_id)
        .order_by(TeamMembership.created_at.asc())
    )
    return list(result.all())
