"""Service and ServiceDependency registry service operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DomainValidationError,
    DuplicateEntityError,
    EntityNotFoundError,
)
from app.models.organization import Organization
from app.models.service import Service, ServiceDependency
from app.schemas.service import ServiceCreate, ServiceDependencyCreate


async def create_service(
    db: AsyncSession,
    organization_id: UUID,
    data: ServiceCreate,
) -> Service:
    """Register a new service within an organization ensuring unique slug per organization."""
    org = await db.get(Organization, organization_id)
    if not org:
        raise EntityNotFoundError(f"Organization '{organization_id}' not found")

    existing = await db.scalar(
        select(Service).where(
            Service.organization_id == organization_id,
            Service.slug == data.slug,
        )
    )
    if existing:
        raise DuplicateEntityError(
            f"Service with slug '{data.slug}' already exists in organization '{organization_id}'"
        )

    service = Service(
        organization_id=organization_id,
        name=data.name,
        slug=data.slug,
        description=data.description,
    )
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


async def get_service(
    db: AsyncSession,
    organization_id: UUID,
    service_id: UUID,
) -> Service:
    """Retrieve a service by ID scoped to its organization."""
    service = await db.get(Service, service_id)
    if not service or service.organization_id != organization_id:
        raise EntityNotFoundError(
            f"Service '{service_id}' not found in organization '{organization_id}'"
        )
    return service


async def list_services(
    db: AsyncSession,
    organization_id: UUID,
) -> list[Service]:
    """List all services belonging to an organization."""
    org = await db.get(Organization, organization_id)
    if not org:
        raise EntityNotFoundError(f"Organization '{organization_id}' not found")

    result = await db.scalars(
        select(Service)
        .where(Service.organization_id == organization_id)
        .order_by(Service.created_at.asc())
    )
    return list(result.all())


async def create_service_dependency(
    db: AsyncSession,
    organization_id: UUID,
    data: ServiceDependencyCreate,
) -> ServiceDependency:
    """Create a directed dependency relationship between two services in the same organization.

    Interpretation:
        source_service_id depends on target_service_id

    Enforces:
    1. No self-dependency (source_service_id != target_service_id).
    2. Both services exist and belong to the specified organization (cross-org rejected).
    3. Duplicate dependency rejection.
    """
    if data.source_service_id == data.target_service_id:
        raise DomainValidationError("A service cannot depend on itself")

    org = await db.get(Organization, organization_id)
    if not org:
        raise EntityNotFoundError(f"Organization '{organization_id}' not found")

    source = await db.get(Service, data.source_service_id)
    if not source:
        raise EntityNotFoundError(f"Source service '{data.source_service_id}' not found")
    if source.organization_id != organization_id:
        raise DomainValidationError("Source service belongs to a different organization")

    target = await db.get(Service, data.target_service_id)
    if not target:
        raise EntityNotFoundError(f"Target service '{data.target_service_id}' not found")
    if target.organization_id != organization_id:
        raise DomainValidationError("Target service belongs to a different organization")

    # Check for duplicate dependency
    existing = await db.scalar(
        select(ServiceDependency).where(
            ServiceDependency.source_service_id == data.source_service_id,
            ServiceDependency.target_service_id == data.target_service_id,
        )
    )
    if existing:
        raise DuplicateEntityError(
            f"Service dependency from '{data.source_service_id}' to '{data.target_service_id}' already exists"
        )

    dependency = ServiceDependency(
        organization_id=organization_id,
        source_service_id=data.source_service_id,
        target_service_id=data.target_service_id,
    )
    db.add(dependency)
    await db.commit()
    await db.refresh(dependency)
    return dependency


async def list_service_dependencies(
    db: AsyncSession,
    organization_id: UUID,
) -> list[ServiceDependency]:
    """List all service dependencies for an organization."""
    org = await db.get(Organization, organization_id)
    if not org:
        raise EntityNotFoundError(f"Organization '{organization_id}' not found")

    result = await db.scalars(
        select(ServiceDependency)
        .where(ServiceDependency.organization_id == organization_id)
        .order_by(ServiceDependency.created_at.asc())
    )
    return list(result.all())
