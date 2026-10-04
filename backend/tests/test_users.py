"""Tests for User API, normalization, and uniqueness constraints."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_retrieve_user(client: AsyncClient) -> None:
    """Verify creating a user and retrieving by ID."""
    payload = {
        "email": "Engineer@IncidentHub.io",
        "display_name": "Senior SRE",
    }
    response = await client.post("/api/v1/users", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "engineer@incidenthub.io"  # lowercase normalized!
    assert data["display_name"] == "Senior SRE"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

    user_id = data["id"]
    get_res = await client.get(f"/api/v1/users/{user_id}")
    assert get_res.status_code == 200
    assert get_res.json()["email"] == "engineer@incidenthub.io"


@pytest.mark.asyncio
async def test_user_email_uniqueness_case_insensitive(client: AsyncClient) -> None:
    """Verify duplicate emails (even with different case) are rejected with 409 Conflict."""
    payload1 = {"email": "dev@incidenthub.io", "display_name": "Dev One"}
    res1 = await client.post("/api/v1/users", json=payload1)
    assert res1.status_code == 201

    payload2 = {"email": "DEV@IncidentHub.io", "display_name": "Dev Duplicate"}
    res2 = await client.post("/api/v1/users", json=payload2)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_user_not_found(client: AsyncClient) -> None:
    """Verify 404 Not Found for non-existent user."""
    random_id = str(uuid.uuid4())
    res = await client.get(f"/api/v1/users/{random_id}")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_user_invalid_uuid(client: AsyncClient) -> None:
    """Verify 422 for invalid user UUID format."""
    res = await client.get("/api/v1/users/invalid-uuid-format")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient) -> None:
    """Verify listing users."""
    await client.post("/api/v1/users", json={"email": "u1@test.com", "display_name": "User 1"})
    await client.post("/api/v1/users", json={"email": "u2@test.com", "display_name": "User 2"})

    res = await client.get("/api/v1/users")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    emails = [i["email"] for i in items]
    assert "u1@test.com" in emails
    assert "u2@test.com" in emails
