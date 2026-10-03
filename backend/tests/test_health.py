import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health_check(client: AsyncClient) -> None:
    """Verify that GET /health returns 200 OK and status 'ok'."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_api_v1_health_check(client: AsyncClient) -> None:
    """Verify that GET /api/v1/health returns 200 OK and status 'ok'."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}
