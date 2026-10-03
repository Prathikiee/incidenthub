from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def get_v1_health() -> HealthResponse:
    """API v1 health status endpoint."""
    return HealthResponse(status="ok")
