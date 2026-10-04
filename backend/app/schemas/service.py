"""Service and ServiceDependency Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ServiceBase(BaseModel):
    """Base fields for service entity."""

    name: str = Field(..., min_length=1, max_length=255, description="Service display name")
    slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="Organization-scoped unique slug (lowercase letters, numbers, and hyphens)",
    )
    description: str | None = Field(
        None, max_length=1000, description="Optional service description"
    )


class ServiceCreate(ServiceBase):
    """Schema for registering a new service in an organization."""

    pass


class ServiceUpdate(BaseModel):
    """Schema for updating an existing service."""

    name: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(
        None, min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    description: str | None = Field(None, max_length=1000)


class ServiceRead(ServiceBase):
    """Schema for reading service details."""

    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceDependencyCreate(BaseModel):
    """Schema for creating a dependency between two services.

    Interpretation:
        source_service_id depends on target_service_id
    """

    source_service_id: UUID = Field(..., description="ID of the dependent service (source)")
    target_service_id: UUID = Field(..., description="ID of the service depended upon (target)")


class ServiceDependencyRead(BaseModel):
    """Schema for reading a service dependency relationship."""

    id: UUID
    organization_id: UUID
    source_service_id: UUID
    target_service_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
