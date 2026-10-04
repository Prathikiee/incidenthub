"""Organization and Team membership Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.membership import OrganizationRole


class OrganizationMembershipBase(BaseModel):
    """Base fields for organization membership."""

    role: OrganizationRole = Field(
        default=OrganizationRole.MEMBER,
        description="Role assigned within the organization",
    )


class OrganizationMembershipCreate(OrganizationMembershipBase):
    """Schema for adding a user to an organization."""

    user_id: UUID = Field(..., description="ID of the user to add as member")


class OrganizationMembershipRead(OrganizationMembershipBase):
    """Schema for reading organization membership."""

    id: UUID
    organization_id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamMembershipCreate(BaseModel):
    """Schema for adding a member to a team."""

    user_id: UUID = Field(..., description="ID of the user to assign to the team")


class TeamMembershipRead(BaseModel):
    """Schema for reading team membership."""

    id: UUID
    team_id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
