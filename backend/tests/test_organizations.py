"""Tests for Organization API and domain constraints."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_retrieve_organization(client: AsyncClient) -> None:
    """Verify creating an organization and retrieving it by ID."""
    payload = {
        "name": "Acme Corp",
        "slug": "acme-corp",
    }
    response = await client.post("/api/v1/organizations", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Corp"
    assert data["slug"] == "acme-corp"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

    org_id = data["id"]
    get_res = await client.get(f"/api/v1/organizations/{org_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == org_id
    assert get_res.json()["name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_organization_slug_uniqueness(client: AsyncClient) -> None:
    """Verify that duplicate organization slugs are rejected with 409 Conflict."""
    payload = {"name": "Org Alpha", "slug": "alpha-corp"}
    res1 = await client.post("/api/v1/organizations", json=payload)
    assert res1.status_code == 201

    # Attempt to create duplicate slug
    res2 = await client.post("/api/v1/organizations", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_organization_not_found(client: AsyncClient) -> None:
    """Verify that non-existent organization returns 404 Not Found."""
    random_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/organizations/{random_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_organization_invalid_uuid(client: AsyncClient) -> None:
    """Verify that malformed UUID returns 422 Unprocessable Entity."""
    response = await client.get("/api/v1/organizations/not-a-valid-uuid")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_organizations(client: AsyncClient) -> None:
    """Verify listing organizations."""
    await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    await client.post("/api/v1/organizations", json={"name": "Org 2", "slug": "org-2"})

    response = await client.get("/api/v1/organizations")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    slugs = [item["slug"] for item in items]
    assert "org-1" in slugs
    assert "org-2" in slugs
