"""Membership service layer operations for Organizations and Teams."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DomainValidationError,
    DuplicateEntityError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.models.membership import (
    OrganizationMembership,
    OrganizationRole,
    TeamMembership,
)
from app.models.organization import Organization
from app.models.team import Team
from app.models.user import User
from app.schemas.membership import OrganizationMembershipCreate, TeamMembershipCreate


async def add_organization_member(
    db: AsyncSession,
    organization_id: UUID,
    data: OrganizationMembershipCreate,
    current_user: User,
    caller_role: OrganizationRole,
) -> OrganizationMembership:
    """Add a user to an organization with a specified role.

    Enforces that:
    1. Users cannot add themselves or self-elevate roles.
    2. Only OWNER may assign ADMIN or OWNER roles. ADMIN may only assign MEMBER or VIEWER.
    3. The organization and target user exist.
    4. Duplicate memberships are rejected.
    """
    # Prevent self-elevation / self-assignment
    if data.user_id == current_user.id:
        raise PermissionDeniedError("Users cannot modify their own membership role")

    # Enforce role assignment hierarchy
    if data.role in (OrganizationRole.ADMIN, OrganizationRole.OWNER):
        if caller_role != OrganizationRole.OWNER:
            raise PermissionDeniedError("Only organization owners can assign ADMIN or OWNER roles")

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


async def update_organization_member_role(
    db: AsyncSession,
    organization_id: UUID,
    target_user_id: UUID,
    new_role: OrganizationRole,
    current_user: User,
    caller_role: OrganizationRole,
) -> OrganizationMembership:
    """Update an existing organization member's role with owner safeguards and hierarchy checks.

    Enforces that:
    1. Users cannot modify their own role.
    2. Only OWNER can modify an existing OWNER's role or assign ADMIN/OWNER roles.
    3. The last OWNER cannot be demoted.
    """
    if target_user_id == current_user.id:
        raise PermissionDeniedError("Users cannot modify their own membership role")

    target_membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == target_user_id,
        )
    )
    if not target_membership:
        raise EntityNotFoundError(
            f"Member '{target_user_id}' not found in organization '{organization_id}'"
        )

    # Protect existing OWNER role
    if target_membership.role == OrganizationRole.OWNER:
        if caller_role != OrganizationRole.OWNER:
            raise PermissionDeniedError("Only organization owners can modify an owner's role")

        if new_role != OrganizationRole.OWNER:
            owner_count = await db.scalar(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(
                    OrganizationMembership.organization_id == organization_id,
                    OrganizationMembership.role == OrganizationRole.OWNER,
                )
            )
            if (owner_count or 0) <= 1:
                raise DomainValidationError("Cannot demote the last owner of an organization")

    # Restrict assignment of privileged roles
    if new_role in (OrganizationRole.ADMIN, OrganizationRole.OWNER):
        if caller_role != OrganizationRole.OWNER:
            raise PermissionDeniedError("Only organization owners can assign ADMIN or OWNER roles")

    target_membership.role = new_role
    await db.commit()
    await db.refresh(target_membership)
    return target_membership


async def remove_organization_member(
    db: AsyncSession,
    organization_id: UUID,
    target_user_id: UUID,
    current_user: User,
    caller_role: OrganizationRole,
) -> None:
    """Remove a member from an organization, enforcing single-owner invariant and privileges.

    Enforces that:
    1. Target member exists in the organization.
    2. Only OWNER may remove another OWNER.
    3. The last OWNER of an organization cannot be removed.
    """
    target_membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == target_user_id,
        )
    )
    if not target_membership:
        raise EntityNotFoundError(
            f"Member '{target_user_id}' not found in organization '{organization_id}'"
        )

    # Check owner removal rules
    if target_membership.role == OrganizationRole.OWNER:
        if caller_role != OrganizationRole.OWNER:
            raise PermissionDeniedError("Only organization owners can remove an owner")

        owner_count = await db.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.role == OrganizationRole.OWNER,
            )
        )
        if (owner_count or 0) <= 1:
            raise DomainValidationError("Cannot remove the last owner of an organization")

    await db.delete(target_membership)
    await db.commit()


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
