"""Tests for Team and Team Membership API, scoping, and constraints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_retrieve_team(client: AsyncClient) -> None:
    """Verify creating a team within an organization and retrieving it."""
    org_res = await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    org_id = org_res.json()["id"]

    team_payload = {
        "name": "Core Infrastructure",
        "description": "Platform reliability squad",
    }
    team_res = await client.post(f"/api/v1/organizations/{org_id}/teams", json=team_payload)
    assert team_res.status_code == 201
    team_data = team_res.json()
    assert team_data["name"] == "Core Infrastructure"
    assert team_data["description"] == "Platform reliability squad"
    assert team_data["organization_id"] == org_id
    assert "id" in team_data
    assert "created_at" in team_data
    assert "updated_at" in team_data

    team_id = team_data["id"]
    get_res = await client.get(f"/api/v1/organizations/{org_id}/teams/{team_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == team_id


@pytest.mark.asyncio
async def test_team_name_uniqueness_within_organization(client: AsyncClient) -> None:
    """Verify team name is unique per organization, but allowed across different organizations."""
    org1_res = await client.post("/api/v1/organizations", json={"name": "Org A", "slug": "org-a"})
    org1_id = org1_res.json()["id"]

    org2_res = await client.post("/api/v1/organizations", json={"name": "Org B", "slug": "org-b"})
    org2_id = org2_res.json()["id"]

    team_payload = {"name": "Security Ops", "description": "SecOps team"}

    # Create team in Org 1
    res1 = await client.post(f"/api/v1/organizations/{org1_id}/teams", json=team_payload)
    assert res1.status_code == 201

    # Attempt duplicate team in Org 1 -> rejected with 409
    res1_dup = await client.post(f"/api/v1/organizations/{org1_id}/teams", json=team_payload)
    assert res1_dup.status_code == 409
    assert "already exists" in res1_dup.json()["detail"].lower()

    # Same team name in Org 2 -> allowed (multi-tenant isolation)
    res2 = await client.post(f"/api/v1/organizations/{org2_id}/teams", json=team_payload)
    assert res2.status_code == 201


@pytest.mark.asyncio
async def test_team_scoping_isolation(client: AsyncClient) -> None:
    """Verify accessing a team from a different organization returns 404."""
    org1_res = await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    org1_id = org1_res.json()["id"]

    org2_res = await client.post("/api/v1/organizations", json={"name": "Org 2", "slug": "org-2"})
    org2_id = org2_res.json()["id"]

    team_res = await client.post(
        f"/api/v1/organizations/{org1_id}/teams",
        json={"name": "Org1 Team"},
    )
    team_id = team_res.json()["id"]

    # Try to access Org1's team via Org2 URL
    cross_res = await client.get(f"/api/v1/organizations/{org2_id}/teams/{team_id}")
    assert cross_res.status_code == 404


@pytest.mark.asyncio
async def test_team_membership_flow_and_tenant_boundary(client: AsyncClient) -> None:
    """Verify team membership requires prior organization membership and rejects duplicates."""
    org_res = await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    org_id = org_res.json()["id"]

    team_res = await client.post(
        f"/api/v1/organizations/{org_id}/teams",
        json={"name": "Database Reliability"},
    )
    team_id = team_res.json()["id"]

    user_res = await client.post(
        "/api/v1/users", json={"email": "dba@test.com", "display_name": "DBA"}
    )
    user_id = user_res.json()["id"]

    # 1. Attempt to add user to team BEFORE user is in organization -> 400 Bad Request
    fail_add = await client.post(
        f"/api/v1/organizations/{org_id}/teams/{team_id}/members",
        json={"user_id": user_id},
    )
    assert fail_add.status_code == 400
    assert "must be an organization member" in fail_add.json()["detail"].lower()

    # 2. Add user to organization
    await client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": user_id, "role": "MEMBER"},
    )

    # 3. Add user to team -> succeeds
    succ_add = await client.post(
        f"/api/v1/organizations/{org_id}/teams/{team_id}/members",
        json={"user_id": user_id},
    )
    assert succ_add.status_code == 201
    assert succ_add.json()["team_id"] == team_id
    assert succ_add.json()["user_id"] == user_id

    # 4. Duplicate team membership attempt -> 409 Conflict
    dup_add = await client.post(
        f"/api/v1/organizations/{org_id}/teams/{team_id}/members",
        json={"user_id": user_id},
    )
    assert dup_add.status_code == 409
    assert "already a member" in dup_add.json()["detail"].lower()

    # 5. List team members
    list_res = await client.get(f"/api/v1/organizations/{org_id}/teams/{team_id}/members")
    assert list_res.status_code == 200
    members = list_res.json()
    assert len(members) == 1
    assert members[0]["user_id"] == user_id
