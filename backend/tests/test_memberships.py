"""Tests for Organization Membership API, roles, and constraints."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_organization_memberships(client: AsyncClient) -> None:
    """Verify adding an organization member and listing members."""
    # Create org
    org_res = await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    org_id = org_res.json()["id"]

    # Create user
    user_res = await client.post(
        "/api/v1/users", json={"email": "alice@test.com", "display_name": "Alice"}
    )
    user_id = user_res.json()["id"]

    # Add member
    mem_res = await client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": user_id, "role": "ADMIN"},
    )
    assert mem_res.status_code == 201
    mem_data = mem_res.json()
    assert mem_data["organization_id"] == org_id
    assert mem_data["user_id"] == user_id
    assert mem_data["role"] == "ADMIN"
    assert "id" in mem_data
    assert "created_at" in mem_data

    # List members
    list_res = await client.get(f"/api/v1/organizations/{org_id}/members")
    assert list_res.status_code == 200
    members = list_res.json()
    assert len(members) == 1
    assert members[0]["user_id"] == user_id


@pytest.mark.asyncio
async def test_duplicate_organization_membership_rejection(client: AsyncClient) -> None:
    """Verify duplicate organization membership is rejected with 409 Conflict."""
    org_res = await client.post(
        "/api/v1/organizations", json={"name": "Org Dup", "slug": "org-dup"}
    )
    org_id = org_res.json()["id"]

    user_res = await client.post(
        "/api/v1/users", json={"email": "bob@test.com", "display_name": "Bob"}
    )
    user_id = user_res.json()["id"]

    res1 = await client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": user_id, "role": "MEMBER"},
    )
    assert res1.status_code == 201

    # Attempt duplicate
    res2 = await client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": user_id, "role": "OWNER"},
    )
    assert res2.status_code == 409
    assert "already a member" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_organization_membership_nonexistent_user(client: AsyncClient) -> None:
    """Verify adding a non-existent user returns 404."""
    org_res = await client.post("/api/v1/organizations", json={"name": "Org X", "slug": "org-x"})
    org_id = org_res.json()["id"]

    res = await client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": str(uuid.uuid4()), "role": "MEMBER"},
    )
    assert res.status_code == 404
    assert "user" in res.json()["detail"].lower()
