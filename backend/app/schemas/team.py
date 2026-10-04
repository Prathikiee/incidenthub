"""Team Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TeamBase(BaseModel):
    """Base fields for team entity."""

    name: str = Field(..., min_length=1, max_length=255, description="Team name")
    description: str | None = Field(None, max_length=1000, description="Optional team description")


class TeamCreate(TeamBase):
    """Schema for creating a new team in an organization."""

    pass


class TeamUpdate(BaseModel):
    """Schema for updating an existing team."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)


class TeamRead(TeamBase):
    """Schema for reading team details."""

    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
