"""Service and ServiceDependency API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.service import (
    ServiceCreate,
    ServiceDependencyCreate,
    ServiceDependencyRead,
    ServiceRead,
)
from app.services import service_registry_service

router = APIRouter(prefix="/organizations/{organization_id}", tags=["services"])


@router.post(
    "/services",
    response_model=ServiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Service",
)
async def create_service_endpoint(
    organization_id: UUID,
    data: ServiceCreate,
    db: AsyncSession = Depends(get_db),
) -> ServiceRead:
    """Register a new service within an organization."""
    service = await service_registry_service.create_service(db, organization_id, data)
    return ServiceRead.model_validate(service)


@router.get(
    "/services",
    response_model=list[ServiceRead],
    summary="List Services",
)
async def list_services_endpoint(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ServiceRead]:
    """List all services belonging to an organization."""
    services = await service_registry_service.list_services(db, organization_id)
    return [ServiceRead.model_validate(s) for s in services]


@router.get(
    "/services/{service_id}",
    response_model=ServiceRead,
    summary="Get Service",
)
async def get_service_endpoint(
    organization_id: UUID,
    service_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ServiceRead:
    """Retrieve service details scoped to an organization."""
    service = await service_registry_service.get_service(db, organization_id, service_id)
    return ServiceRead.model_validate(service)


@router.post(
    "/service-dependencies",
    response_model=ServiceDependencyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Service Dependency",
)
async def create_service_dependency_endpoint(
    organization_id: UUID,
    data: ServiceDependencyCreate,
    db: AsyncSession = Depends(get_db),
) -> ServiceDependencyRead:
    """Declare a directed dependency relationship between two services in an organization.

    Interpretation:
        source_service_id depends on target_service_id
    """
    dep = await service_registry_service.create_service_dependency(db, organization_id, data)
    return ServiceDependencyRead.model_validate(dep)


@router.get(
    "/service-dependencies",
    response_model=list[ServiceDependencyRead],
    summary="List Service Dependencies",
)
async def list_service_dependencies_endpoint(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ServiceDependencyRead]:
    """List all service dependencies within an organization."""
    deps = await service_registry_service.list_service_dependencies(db, organization_id)
    return [ServiceDependencyRead.model_validate(d) for d in deps]
