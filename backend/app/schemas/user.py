"""User Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_PATTERN = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class UserBase(BaseModel):
    """Base fields for user entity."""

    email: str = Field(
        ...,
        pattern=EMAIL_PATTERN,
        max_length=255,
        description="User's unique email address",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's full display name",
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email address to lowercase and strip whitespace."""
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserCreate(UserBase):
    """Schema for registering a new user."""

    is_active: bool = Field(default=True, description="Account active status")


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    display_name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None


class UserRead(UserBase):
    """Schema for reading user details."""

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
