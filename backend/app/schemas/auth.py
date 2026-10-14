"""Authentication Pydantic schemas for request and response models."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.user import EMAIL_PATTERN, UserRead


class RegisterRequest(BaseModel):
    """Schema for user registration request."""

    email: str = Field(
        ...,
        pattern=EMAIL_PATTERN,
        max_length=255,
        description="Unique user email address",
    )
    password: str = Field(
        ...,
        max_length=128,
        description="User password meeting complexity policy",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full display name of the user",
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email address to lowercase and strip whitespace."""
        if isinstance(v, str):
            return v.strip().lower()
        return v


class LoginRequest(BaseModel):
    """Schema for user login credentials."""

    email: str = Field(
        ...,
        max_length=255,
        description="Registered user email",
    )
    password: str = Field(
        ...,
        max_length=128,
        description="User password",
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email address to lowercase and strip whitespace."""
        if isinstance(v, str):
            return v.strip().lower()
        return v


class TokenResponse(BaseModel):
    """Schema for successful authentication response containing token pair."""

    access_token: str = Field(..., description="Signed JWT access token")
    refresh_token: str = Field(..., description="Opaque raw refresh token")
    token_type: str = Field(default="bearer", description="Token type identifier")
    expires_in: int = Field(..., description="Access token lifespan duration in seconds")
    user: UserRead = Field(..., description="Authenticated user profile")

    model_config = ConfigDict(from_attributes=True)


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Raw refresh token to rotate",
    )


class RefreshTokenResponse(BaseModel):
    """Schema for refreshed token pair response."""

    access_token: str = Field(..., description="Newly issued JWT access token")
    refresh_token: str = Field(..., description="Newly issued rotated raw refresh token")
    token_type: str = Field(default="bearer", description="Token type identifier")
    expires_in: int = Field(..., description="Access token lifespan duration in seconds")
    user: UserRead | None = Field(default=None, description="Authenticated user profile")

    model_config = ConfigDict(from_attributes=True)


class LogoutRequest(BaseModel):
    """Schema for explicit user session logout."""

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Raw refresh token to revoke",
    )


class TokenPayload(BaseModel):
    """Decoded JWT access token claims payload."""

    sub: UUID = Field(..., description="Subject identifier (user UUID)")
    email: str = Field(..., description="User email claim")
    type: str = Field(default="access", description="Token type claim")
    exp: int = Field(..., description="Expiration timestamp (Unix epoch)")
    iat: int = Field(..., description="Issued-at timestamp (Unix epoch)")
    jti: str | None = Field(default=None, description="Unique token JWT ID")
