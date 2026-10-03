"""IncidentHub FastAPI Application Entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.schemas.health import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup and shutdown events."""
    # Startup tasks (e.g. connection pool checks, telemetry)
    yield
    # Shutdown tasks (e.g. dispose engines, close connections)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Incident intelligence and response workspace foundation",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Top-level health check endpoint
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Application Health Check",
)
async def health_check() -> HealthResponse:
    """Return application operational health status."""
    return HealthResponse(status="ok")


# Mount versioned API router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
