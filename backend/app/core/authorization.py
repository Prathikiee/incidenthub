"""Multi-tenant authorization dependencies, context resolution, and RBAC guards."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.core.security import get_current_active_user
from app.db.session import get_db
from app.models.membership import OrganizationMembership, OrganizationRole
from app.models.organization import Organization
from app.models.user import User


@dataclass(frozen=True)
class OrganizationContext:
    """Resolved tenant context representing verified organization membership and role."""

    organization: Organization
    user: User
    role: OrganizationRole
    membership: OrganizationMembership


async def get_organization_context(
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationContext:
    """Resolve and verify active organization context for the authenticated user.

    Enforces that:
    1. The caller is an authenticated, active user (via get_current_active_user).
    2. The caller has an active membership record in the target organization.

    Security Policy:
    If the caller is not a member of the organization (or if the organization does not exist),
    raises EntityNotFoundError (HTTP 404). This prevents organization existence enumeration
    by returning identical 404 responses for non-existent and unauthorized organizations.
    """
    stmt = (
        select(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise EntityNotFoundError(f"Organization '{organization_id}' not found")

    membership, organization = row
    return OrganizationContext(
        organization=organization,
        user=current_user,
        role=membership.role,
        membership=membership,
    )


def require_org_role(
    *allowed_roles: OrganizationRole,
) -> Callable[..., Coroutine[Any, Any, OrganizationContext]]:
    """Dependency factory enforcing that the authenticated user possesses one of the allowed roles.

    Raises PermissionDeniedError (HTTP 403) if the user's role is not in allowed_roles.
    """

    async def role_checker(
        ctx: OrganizationContext = Depends(get_organization_context),
    ) -> OrganizationContext:
        if ctx.role not in allowed_roles:
            raise PermissionDeniedError("Insufficient permissions for this organization operation")
        return ctx

    return role_checker


# Declarative role-based dependency shortcuts matching the Milestone 3 RBAC matrix:
# OWNER: Full administrative control, ownership transfer, organization deletion.
require_owner = require_org_role(OrganizationRole.OWNER)

# ADMIN or OWNER: Member management (MEMBER/VIEWER), team creation/modification.
require_admin = require_org_role(OrganizationRole.OWNER, OrganizationRole.ADMIN)

# MEMBER, ADMIN, or OWNER: Service registration, updating, and dependency declaration.
require_member = require_org_role(
    OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.MEMBER
)

# Any active organization member: Read access to organization, services, teams, members.
require_viewer = require_org_role(
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.MEMBER,
    OrganizationRole.VIEWER,
)
