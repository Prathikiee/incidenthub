"""Tests for ServiceDependency API, directed edges, and multi-tenant constraints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_service_dependencies(client: AsyncClient) -> None:
    """Verify creating a dependency edge between two services in the same organization."""
    # 1. Create Organization
    org_res = await client.post(
        "/api/v1/organizations", json={"name": "Retail Corp", "slug": "retail-corp"}
    )
    org_id = org_res.json()["id"]

    # 2. Create Checkout API (source) and Payment Service (target)
    source_res = await client.post(
        f"/api/v1/organizations/{org_id}/services",
        json={"name": "Checkout API", "slug": "checkout-api"},
    )
    source_id = source_res.json()["id"]

    target_res = await client.post(
        f"/api/v1/organizations/{org_id}/services",
        json={"name": "Payment Service", "slug": "payment-service"},
    )
    target_id = target_res.json()["id"]

    # 3. Create dependency: Checkout API depends on Payment Service
    dep_payload = {
        "source_service_id": source_id,
        "target_service_id": target_id,
    }
    dep_res = await client.post(
        f"/api/v1/organizations/{org_id}/service-dependencies",
        json=dep_payload,
    )
    assert dep_res.status_code == 201
    dep_data = dep_res.json()
    assert dep_data["organization_id"] == org_id
    assert dep_data["source_service_id"] == source_id
    assert dep_data["target_service_id"] == target_id
    assert "id" in dep_data
    assert "created_at" in dep_data

    # 4. List dependencies
    list_res = await client.get(f"/api/v1/organizations/{org_id}/service-dependencies")
    assert list_res.status_code == 200
    deps = list_res.json()
    assert len(deps) == 1
    assert deps[0]["source_service_id"] == source_id
    assert deps[0]["target_service_id"] == target_id


@pytest.mark.asyncio
async def test_self_dependency_rejection(client: AsyncClient) -> None:
    """Verify that a service cannot depend on itself (rejected with 400 Bad Request)."""
    org_res = await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    org_id = org_res.json()["id"]

    svc_res = await client.post(
        f"/api/v1/organizations/{org_id}/services",
        json={"name": "Service Loop", "slug": "service-loop"},
    )
    svc_id = svc_res.json()["id"]

    # Attempt self-dependency
    res = await client.post(
        f"/api/v1/organizations/{org_id}/service-dependencies",
        json={"source_service_id": svc_id, "target_service_id": svc_id},
    )
    assert res.status_code == 400
    assert "cannot depend on itself" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_duplicate_dependency_rejection(client: AsyncClient) -> None:
    """Verify duplicate directed dependencies are rejected with 409 Conflict."""
    org_res = await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    org_id = org_res.json()["id"]

    s1_res = await client.post(
        f"/api/v1/organizations/{org_id}/services",
        json={"name": "Frontend Web", "slug": "frontend-web"},
    )
    s1_id = s1_res.json()["id"]

    s2_res = await client.post(
        f"/api/v1/organizations/{org_id}/services",
        json={"name": "Backend API", "slug": "backend-api"},
    )
    s2_id = s2_res.json()["id"]

    # First dependency creation succeeds
    res1 = await client.post(
        f"/api/v1/organizations/{org_id}/service-dependencies",
        json={"source_service_id": s1_id, "target_service_id": s2_id},
    )
    assert res1.status_code == 201

    # Second duplicate dependency creation fails
    res2 = await client.post(
        f"/api/v1/organizations/{org_id}/service-dependencies",
        json={"source_service_id": s1_id, "target_service_id": s2_id},
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cross_organization_dependency_rejection(client: AsyncClient) -> None:
    """Verify that dependencies cannot cross organization boundaries."""
    org1_res = await client.post("/api/v1/organizations", json={"name": "Org 1", "slug": "org-1"})
    org1_id = org1_res.json()["id"]

    org2_res = await client.post("/api/v1/organizations", json={"name": "Org 2", "slug": "org-2"})
    org2_id = org2_res.json()["id"]

    svc1_res = await client.post(
        f"/api/v1/organizations/{org1_id}/services",
        json={"name": "Org1 Service", "slug": "org1-service"},
    )
    svc1_id = svc1_res.json()["id"]

    svc2_res = await client.post(
        f"/api/v1/organizations/{org2_id}/services",
        json={"name": "Org2 Service", "slug": "org2-service"},
    )
    svc2_id = svc2_res.json()["id"]

    # Attempt to create dependency from Org1 service to Org2 service under Org1 scope
    res = await client.post(
        f"/api/v1/organizations/{org1_id}/service-dependencies",
        json={"source_service_id": svc1_id, "target_service_id": svc2_id},
    )
    assert res.status_code == 400
    assert "different organization" in res.json()["detail"].lower()
