"""IncidentHub API v1 master router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    health,
    organizations,
    services,
    teams,
    users,
)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(organizations.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(teams.router)
api_v1_router.include_router(services.router)
