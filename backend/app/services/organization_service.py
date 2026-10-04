"""Organization service layer operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateEntityError, EntityNotFoundError
from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate


async def create_organization(db: AsyncSession, data: OrganizationCreate) -> Organization:
    """Create a new organization ensuring unique slug."""
    existing = await db.scalar(select(Organization).where(Organization.slug == data.slug))
    if existing:
        raise DuplicateEntityError(f"Organization with slug '{data.slug}' already exists")

    org = Organization(name=data.name, slug=data.slug)
    db.add(org)
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
