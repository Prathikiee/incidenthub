"""Organization service layer operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateEntityError, EntityNotFoundError
from app.models.membership import OrganizationMembership, OrganizationRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationCreate


async def create_organization(
    db: AsyncSession,
    data: OrganizationCreate,
    creator: User,
) -> Organization:
    """Create a new organization and atomically assign the creator as OWNER.

    Enforces that:
    1. Organization slug is unique across the platform.
    2. Creator is atomically assigned as OWNER within the same database transaction,
       guaranteeing an organization is never left without its initial owner.
    """
    existing = await db.scalar(select(Organization).where(Organization.slug == data.slug))
    if existing:
        raise DuplicateEntityError(f"Organization with slug '{data.slug}' already exists")

    org = Organization(name=data.name, slug=data.slug)
    db.add(org)
    await db.flush()

    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=creator.id,
        role=OrganizationRole.OWNER,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(org)
    return org


async def get_organization(db: AsyncSession, organization_id: UUID) -> Organization:
    """Retrieve an organization by its ID or raise EntityNotFoundError."""
    org = await db.get(Organization, organization_id)
    if not org:
        raise EntityNotFoundError(f"Organization '{organization_id}' not found")
    return org


async def get_organization_by_slug(db: AsyncSession, slug: str) -> Organization | None:
    """Retrieve an organization by its unique slug."""
    return await db.scalar(select(Organization).where(Organization.slug == slug))


async def list_user_organizations(
    db: AsyncSession,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[Organization]:
    """List organizations for which the user holds an active membership."""
    stmt = (
        select(Organization)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(OrganizationMembership.user_id == user_id)
        .order_by(Organization.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def list_organizations(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
) -> list[Organization]:
    """List organizations ordered by creation date."""
    result = await db.scalars(
        select(Organization).offset(skip).limit(limit).order_by(Organization.created_at.desc())
    )
    return list(result.all())
