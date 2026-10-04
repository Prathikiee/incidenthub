"""Tests for Service API, multi-tenant uniqueness, and retrieval."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_retrieve_service(client: AsyncClient) -> None:
    """Verify creating a service within an organization and retrieving it."""
    org_res = await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    org_id = org_res.json()["id"]

    service_payload = {
        "name": "Auth Service",
        "slug": "auth-service",
        "description": "Handles authentication and token issuance",
    }
    svc_res = await client.post(
        f"/api/v1/organizations/{org_id}/services",
        json=service_payload,
    )
    assert svc_res.status_code == 201
    svc_data = svc_res.json()
    assert svc_data["name"] == "Auth Service"
    assert svc_data["slug"] == "auth-service"
    assert svc_data["description"] == "Handles authentication and token issuance"
    assert svc_data["organization_id"] == org_id
    assert "id" in svc_data
    assert "created_at" in svc_data
    assert "updated_at" in svc_data

    service_id = svc_data["id"]
    get_res = await client.get(f"/api/v1/organizations/{org_id}/services/{service_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == service_id


@pytest.mark.asyncio
async def test_service_slug_uniqueness_within_organization(client: AsyncClient) -> None:
    """Verify service slug is unique per organization, but allowed across different organizations."""
    org1_res = await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    org1_id = org1_res.json()["id"]

    org2_res = await client.post("/api/v1/organizations", json={"name": "Org 2", "slug": "org-2"})
    org2_id = org2_res.json()["id"]

    payload = {"name": "Payment Gateway", "slug": "payment-gateway"}

    # Create in Org 1
    res1 = await client.post(f"/api/v1/organizations/{org1_id}/services", json=payload)
    assert res1.status_code == 201

    # Duplicate in Org 1 -> rejected with 409
    res1_dup = await client.post(f"/api/v1/organizations/{org1_id}/services", json=payload)
    assert res1_dup.status_code == 409
    assert "already exists" in res1_dup.json()["detail"].lower()

    # Same slug in Org 2 -> allowed (multi-tenancy)
    res2 = await client.post(f"/api/v1/organizations/{org2_id}/services", json=payload)
    assert res2.status_code == 201


@pytest.mark.asyncio
async def test_service_scoping_isolation(client: AsyncClient) -> None:
    """Verify cross-organization service access returns 404."""
    org1_res = await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    org1_id = org1_res.json()["id"]

    org2_res = await client.post("/api/v1/organizations", json={"name": "Org 2", "slug": "org-2"})
    org2_id = org2_res.json()["id"]

    svc_res = await client.post(
        f"/api/v1/organizations/{org1_id}/services",
        json={"name": "Inventory API", "slug": "inventory-api"},
    )
    svc_id = svc_res.json()["id"]

    # Try to access via Org 2 URL
    res = await client.get(f"/api/v1/organizations/{org2_id}/services/{svc_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_services_scoped_to_organization(client: AsyncClient) -> None:
    """Verify listing services only returns services for the target organization."""
    org1_res = await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    org1_id = org1_res.json()["id"]

    org2_res = await client.post("/api/v1/organizations", json={"name": "Org 2", "slug": "org-2"})
    org2_id = org2_res.json()["id"]

    await client.post(
        f"/api/v1/organizations/{org1_id}/services",
        json={"name": "Service 1", "slug": "service-1"},
    )
    await client.post(
        f"/api/v1/organizations/{org1_id}/services",
        json={"name": "Service 2", "slug": "service-2"},
    )
    await client.post(
        f"/api/v1/organizations/{org2_id}/services",
        json={"name": "Service 3", "slug": "service-3"},
    )

    list1 = await client.get(f"/api/v1/organizations/{org1_id}/services")
    assert list1.status_code == 200
    assert len(list1.json()) == 2

    list2 = await client.get(f"/api/v1/organizations/{org2_id}/services")
    assert list2.status_code == 200
    assert len(list2.json()) == 1
    assert list2.json()[0]["slug"] == "service-3"
