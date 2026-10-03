from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Schema for health check responses."""

    model_config = ConfigDict(extra="forbid")

    status: str
