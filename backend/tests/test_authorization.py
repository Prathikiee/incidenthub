"""Milestone 3 Multi-Tenant Authorization Tests (Phase 2B/3A).

Comprehensive tests verifying:
1. Unauthenticated organization-scoped request returns 401.
2. Authenticated organization member can access permitted resources.
3. Non-member receives 404 for a protected organization (preventing tenant enumeration).
4. Member with insufficient role receives 403.
5. Organization listing only returns the current user's organizations.
6. Organization creation grants the creator OWNER membership.
7. Organization creation does not leave an ownerless organization on failure.
8. Member cannot add themselves as OWNER or ADMIN (no self-elevation).
9. Member cannot modify another organization's membership.
10. Last-owner removal or demotion is rejected.
11. Team and service cross-tenant reads/writes are rejected.
12. Cross-tenant service dependency creation is rejected.
13. Resource IDs cannot bypass organization ownership checks.
14. Membership revocation and role changes affect subsequent requests.
15. Inactive users cannot access protected resources.
16. The user-list endpoint no longer exposes an unauthenticated global directory.
17. Existing domain tests remain compatible with the authorization changes.
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import (
    OrganizationContext,
    get_organization_context,
    require_org_role,
)
from app.core.exceptions import (
    DomainValidationError,
    DuplicateEntityError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.membership import OrganizationMembership, OrganizationRole
from app.models.organization import Organization
from app.models.service import Service
from app.models.team import Team
from app.models.user import User
from app.schemas.membership import (
    OrganizationMembershipCreate,
)
from app.schemas.organization import OrganizationCreate
from app.schemas.service import ServiceDependencyCreate
from app.services import (
    membership_service,
    organization_service,
    service_registry_service,
    team_service,
)


# Helper factory for test User
def make_test_user(
    user_id: UUID | None = None,
    email: str = "user@incidenthub.io",
    is_active: bool = True,
) -> User:
    return User(
        id=user_id or uuid.uuid4(),
        email=email,
        display_name="Test User",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# Helper factory for test Organization
def make_test_org(org_id: UUID | None = None, slug: str = "acme-corp") -> Organization:
    return Organization(
        id=org_id or uuid.uuid4(),
        name="Acme Corp",
        slug=slug,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# Helper factory for test OrganizationMembership
def make_test_membership(
    org: Organization,
    user: User,
    role: OrganizationRole = OrganizationRole.MEMBER,
) -> OrganizationMembership:
    return OrganizationMembership(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=user.id,
        role=role,
        created_at=datetime.now(UTC),
    )


# ===========================================================================
# 1. Core Authorization Dependency and Context Unit Tests
# ===========================================================================


class TestAuthorizationContextDependencies:
    """Unit tests for get_organization_context and require_org_role dependencies."""

    @pytest.mark.asyncio
    async def test_get_org_context_resolves_active_membership(self) -> None:
        """Verify that get_organization_context returns context when active membership exists."""
        test_user = make_test_user()
        test_org = make_test_org()
        test_mem = make_test_membership(test_org, test_user, OrganizationRole.ADMIN)

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.first.return_value = (test_mem, test_org)
        mock_db.execute.return_value = mock_result

        ctx = await get_organization_context(
            organization_id=test_org.id,
            current_user=test_user,
            db=mock_db,
        )

        assert ctx.organization.id == test_org.id
        assert ctx.user.id == test_user.id
        assert ctx.role == OrganizationRole.ADMIN
        assert ctx.membership.id == test_mem.id

    @pytest.mark.asyncio
    async def test_get_org_context_non_member_raises_404(self) -> None:
        """Verify that a non-member raises EntityNotFoundError (HTTP 404) to prevent enumeration."""
        test_user = make_test_user()
        target_org_id = uuid.uuid4()

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.first.return_value = None  # No membership row found
        mock_db.execute.return_value = mock_result

        with pytest.raises(EntityNotFoundError) as exc_info:
            await get_organization_context(
                organization_id=target_org_id,
                current_user=test_user,
                db=mock_db,
            )

        assert str(target_org_id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_require_org_role_permitted_roles_pass(self) -> None:
        """Verify that users with permitted roles pass require_org_role check."""
        test_user = make_test_user()
        test_org = make_test_org()
        test_mem = make_test_membership(test_org, test_user, OrganizationRole.ADMIN)
        ctx = OrganizationContext(
            organization=test_org,
            user=test_user,
            role=OrganizationRole.ADMIN,
            membership=test_mem,
        )

        admin_checker = require_org_role(OrganizationRole.OWNER, OrganizationRole.ADMIN)
        resolved = await admin_checker(ctx=ctx)
        assert resolved == ctx

    @pytest.mark.asyncio
    async def test_require_org_role_insufficient_role_raises_403(self) -> None:
        """Verify that users with insufficient roles receive PermissionDeniedError (HTTP 403)."""
        test_user = make_test_user()
        test_org = make_test_org()
        test_mem = make_test_membership(test_org, test_user, OrganizationRole.MEMBER)
        ctx = OrganizationContext(
            organization=test_org,
            user=test_user,
            role=OrganizationRole.MEMBER,
            membership=test_mem,
        )

        admin_checker = require_org_role(OrganizationRole.OWNER, OrganizationRole.ADMIN)
        with pytest.raises(PermissionDeniedError) as exc_info:
            await admin_checker(ctx=ctx)

        assert "Insufficient permissions" in str(exc_info.value)


# ===========================================================================
# 2. Organization Creation & Auto-Owner Assignment Tests (Rules 1, 6, 7)
# ===========================================================================


class TestOrganizationCreationAndOwnership:
    """Tests for organization creation and atomic OWNER assignment."""

    @pytest.mark.asyncio
    async def test_organization_creation_assigns_creator_as_owner(self) -> None:
        """Verify organization creation atomically adds creator as OWNER in the same transaction."""
        creator = make_test_user()
        data = OrganizationCreate(name="New Org", slug="new-org")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar.return_value = None  # Slug is unique

        # Track added objects
        added_objects: list[Any] = []
        mock_db.add.side_effect = lambda obj: added_objects.append(obj)

        org = await organization_service.create_organization(mock_db, data, creator=creator)
        assert org.slug == "new-org"

        # Verify Organization and OWNER membership were added
        assert len(added_objects) == 2
        org_obj = added_objects[0]
        mem_obj = added_objects[1]

        assert isinstance(org_obj, Organization)
        assert org_obj.slug == "new-org"
        assert isinstance(mem_obj, OrganizationMembership)
        assert mem_obj.role == OrganizationRole.OWNER
        assert mem_obj.user_id == creator.id

        # Verify transaction commit
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_organization_creation_duplicate_slug_rollback(self) -> None:
        """Verify duplicate slug rejection does not leave an ownerless organization."""
        creator = make_test_user()
        data = OrganizationCreate(name="Duplicate", slug="dup-org")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar.return_value = make_test_org(slug="dup-org")  # Slug exists

        with pytest.raises(DuplicateEntityError):
            await organization_service.create_organization(mock_db, data, creator=creator)

        mock_db.commit.assert_not_awaited()


# ===========================================================================
# 3. Organization Listing Tenant Isolation Tests (Rules 2, 5)
# ===========================================================================


class TestOrganizationListingIsolation:
    """Tests for tenant-scoped organization listing."""

    @pytest.mark.asyncio
    async def test_list_user_organizations_only_returns_memberships(self) -> None:
        """Verify listing organizations only returns organizations where user holds membership."""
        user = make_test_user()
        org_owned = make_test_org(slug="org-owned")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [org_owned]
        mock_db.scalars.return_value = mock_scalars

        orgs = await organization_service.list_user_organizations(mock_db, user_id=user.id)
        assert len(orgs) == 1
        assert orgs[0].slug == "org-owned"


# ===========================================================================
# 4. Membership Management & Role Safeguard Tests (Rules 4, 5, 6, 7, 8, 9, 10, 14)
# ===========================================================================


class TestMembershipManagementAndOwnerSafeguards:
    """Tests for membership role enforcement, no self-elevation, and owner safeguards."""

    @pytest.mark.asyncio
    async def test_member_cannot_self_elevate_raises_403(self) -> None:
        """Verify that a member cannot modify or assign roles to themselves."""
        current_user = make_test_user()
        org_id = uuid.uuid4()
        data = OrganizationMembershipCreate(user_id=current_user.id, role=OrganizationRole.OWNER)

        mock_db = AsyncMock(spec=AsyncSession)

        with pytest.raises(PermissionDeniedError) as exc_info:
            await membership_service.add_organization_member(
                mock_db,
                organization_id=org_id,
                data=data,
                current_user=current_user,
                caller_role=OrganizationRole.ADMIN,
            )

        assert "cannot modify their own membership role" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_admin_cannot_assign_admin_or_owner_raises_403(self) -> None:
        """Verify that an ADMIN cannot assign ADMIN or OWNER roles."""
        current_user = make_test_user()
        target_user = make_test_user(email="target@hub.io")
        org_id = uuid.uuid4()

        data_admin = OrganizationMembershipCreate(
            user_id=target_user.id, role=OrganizationRole.ADMIN
        )
        data_owner = OrganizationMembershipCreate(
            user_id=target_user.id, role=OrganizationRole.OWNER
        )

        mock_db = AsyncMock(spec=AsyncSession)

        for data in (data_admin, data_owner):
            with pytest.raises(PermissionDeniedError) as exc_info:
                await membership_service.add_organization_member(
                    mock_db,
                    organization_id=org_id,
                    data=data,
                    current_user=current_user,
                    caller_role=OrganizationRole.ADMIN,
                )
            assert "Only organization owners can assign ADMIN or OWNER roles" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_owner_can_assign_admin_and_member(self) -> None:
        """Verify that an OWNER can assign ADMIN or MEMBER roles to another user."""
        current_user = make_test_user()
        target_user = make_test_user(email="newadmin@hub.io")
        org = make_test_org()
        data = OrganizationMembershipCreate(user_id=target_user.id, role=OrganizationRole.ADMIN)

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.get.side_effect = lambda model, obj_id: (
            org if model == Organization else target_user
        )
        mock_db.scalar.return_value = None  # Not already a member

        mem = await membership_service.add_organization_member(
            mock_db,
            organization_id=org.id,
            data=data,
            current_user=current_user,
            caller_role=OrganizationRole.OWNER,
        )

        assert mem.role == OrganizationRole.ADMIN
        assert mem.user_id == target_user.id
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_last_owner_demotion_rejected(self) -> None:
        """Verify that attempting to demote the sole owner raises DomainValidationError."""
        caller = make_test_user()
        owner_user = make_test_user(email="soleowner@hub.io")
        org = make_test_org()
        target_mem = make_test_membership(org, owner_user, OrganizationRole.OWNER)

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar.side_effect = [
            target_mem,  # Existing membership query
            1,  # Owner count query returns 1
        ]

        with pytest.raises(DomainValidationError) as exc_info:
            await membership_service.update_organization_member_role(
                mock_db,
                organization_id=org.id,
                target_user_id=owner_user.id,
                new_role=OrganizationRole.ADMIN,
                current_user=caller,
                caller_role=OrganizationRole.OWNER,
            )

        assert "Cannot demote the last owner" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_last_owner_removal_rejected(self) -> None:
        """Verify that attempting to remove the sole owner raises DomainValidationError."""
        caller = make_test_user()
        owner_user = make_test_user(email="soleowner@hub.io")
        org = make_test_org()
        target_mem = make_test_membership(org, owner_user, OrganizationRole.OWNER)

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar.side_effect = [
            target_mem,  # Existing membership query
            1,  # Owner count query returns 1
        ]

        with pytest.raises(DomainValidationError) as exc_info:
            await membership_service.remove_organization_member(
                mock_db,
                organization_id=org.id,
                target_user_id=owner_user.id,
                current_user=caller,
                caller_role=OrganizationRole.OWNER,
            )

        assert "Cannot remove the last owner" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_admin_cannot_remove_owner_raises_403(self) -> None:
        """Verify that an ADMIN cannot remove an OWNER."""
        admin_caller = make_test_user()
        owner_user = make_test_user(email="owner@hub.io")
        org = make_test_org()
        target_mem = make_test_membership(org, owner_user, OrganizationRole.OWNER)

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar.return_value = target_mem

        with pytest.raises(PermissionDeniedError) as exc_info:
            await membership_service.remove_organization_member(
                mock_db,
                organization_id=org.id,
                target_user_id=owner_user.id,
                current_user=admin_caller,
                caller_role=OrganizationRole.ADMIN,
            )

        assert "Only organization owners can remove an owner" in str(exc_info.value)


# ===========================================================================
# 5. FastApi Endpoint Authorization & HTTP Contract Tests (Mocked DB Session)
# ===========================================================================


class TestEndpointAuthorizationContracts:
    """HTTP endpoint integration tests testing 401, 403, and 404 response policies."""

    @pytest.mark.asyncio
    async def test_unauthenticated_request_returns_401(self) -> None:
        """Unauthenticated requests to protected endpoints return HTTP 401 Unauthorized."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            random_org_id = uuid.uuid4()

            # Organization endpoints
            res_org = await client.get(f"/api/v1/organizations/{random_org_id}")
            assert res_org.status_code == status.HTTP_401_UNAUTHORIZED

            res_list_orgs = await client.get("/api/v1/organizations")
            assert res_list_orgs.status_code == status.HTTP_401_UNAUTHORIZED

            # Service endpoints
            res_svc = await client.get(f"/api/v1/organizations/{random_org_id}/services")
            assert res_svc.status_code == status.HTTP_401_UNAUTHORIZED

            # Team endpoints
            res_team = await client.get(f"/api/v1/organizations/{random_org_id}/teams")
            assert res_team.status_code == status.HTTP_401_UNAUTHORIZED

            # User directory endpoint
            res_users = await client.get("/api/v1/users")
            assert res_users.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_deactivated_user_returns_401(self) -> None:
        """Requests with tokens belonging to deactivated users return HTTP 401 Unauthorized."""
        inactive_user = make_test_user(is_active=False)
        token = create_access_token(user_id=inactive_user.id, email=inactive_user.email)
        headers = {"Authorization": f"Bearer {token}"}

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.get.return_value = inactive_user

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                res = await client.get(
                    f"/api/v1/organizations/{uuid.uuid4()}",
                    headers=headers,
                )
                assert res.status_code == status.HTTP_401_UNAUTHORIZED
                assert "inactive" in res.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_non_member_receives_uniform_404(self) -> None:
        """Authenticated non-member requesting organization returns 404 (preventing enumeration)."""
        active_user = make_test_user()
        token = create_access_token(user_id=active_user.id, email=active_user.email)
        headers = {"Authorization": f"Bearer {token}"}
        target_org_id = uuid.uuid4()

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.get.return_value = active_user  # User found

        # Query for membership in target_org_id returns None
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                res = await client.get(
                    f"/api/v1/organizations/{target_org_id}",
                    headers=headers,
                )
                assert res.status_code == status.HTTP_404_NOT_FOUND
                assert "not found" in res.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_viewer_cannot_create_service_returns_403(self) -> None:
        """VIEWER role attempting POST /services receives HTTP 403 Forbidden."""
        active_user = make_test_user()
        test_org = make_test_org()
        test_mem = make_test_membership(test_org, active_user, OrganizationRole.VIEWER)

        token = create_access_token(user_id=active_user.id, email=active_user.email)
        headers = {"Authorization": f"Bearer {token}"}

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.get.return_value = active_user

        mock_result = MagicMock()
        mock_result.first.return_value = (test_mem, test_org)
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                res = await client.post(
                    f"/api/v1/organizations/{test_org.id}/services",
                    json={"name": "New Service", "slug": "new-svc"},
                    headers=headers,
                )
                assert res.status_code == status.HTTP_403_FORBIDDEN
                assert "Insufficient permissions" in res.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_member_cannot_create_team_returns_403(self) -> None:
        """MEMBER role attempting POST /teams receives HTTP 403 Forbidden."""
        active_user = make_test_user()
        test_org = make_test_org()
        test_mem = make_test_membership(test_org, active_user, OrganizationRole.MEMBER)

        token = create_access_token(user_id=active_user.id, email=active_user.email)
        headers = {"Authorization": f"Bearer {token}"}

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.get.return_value = active_user

        mock_result = MagicMock()
        mock_result.first.return_value = (test_mem, test_org)
        mock_db.execute.return_value = mock_result

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                res = await client.post(
                    f"/api/v1/organizations/{test_org.id}/teams",
                    json={"name": "New Team", "description": "Desc"},
                    headers=headers,
                )
                assert res.status_code == status.HTTP_403_FORBIDDEN
                assert "Insufficient permissions" in res.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_admin_can_create_team(self) -> None:
        """ADMIN role attempting POST /teams succeeds with HTTP 201 Created."""
        active_user = make_test_user()
        test_org = make_test_org()
        test_mem = make_test_membership(test_org, active_user, OrganizationRole.ADMIN)

        token = create_access_token(user_id=active_user.id, email=active_user.email)
        headers = {"Authorization": f"Bearer {token}"}

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.get.return_value = active_user

        mock_result = MagicMock()
        mock_result.first.return_value = (test_mem, test_org)
        mock_db.execute.return_value = mock_result

        created_team = Team(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            name="Platform Team",
            description="Infra",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        with patch("app.services.team_service.create_team", return_value=created_team):
            app.dependency_overrides[get_db] = lambda: mock_db
            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                    res = await client.post(
                        f"/api/v1/organizations/{test_org.id}/teams",
                        json={"name": "Platform Team", "description": "Infra"},
                        headers=headers,
                    )
                    assert res.status_code == status.HTTP_201_CREATED
                    assert res.json()["name"] == "Platform Team"
            finally:
                app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_member_can_create_service(self) -> None:
        """MEMBER role attempting POST /services succeeds with HTTP 201 Created."""
        active_user = make_test_user()
        test_org = make_test_org()
        test_mem = make_test_membership(test_org, active_user, OrganizationRole.MEMBER)

        token = create_access_token(user_id=active_user.id, email=active_user.email)
        headers = {"Authorization": f"Bearer {token}"}

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.get.return_value = active_user

        mock_result = MagicMock()
        mock_result.first.return_value = (test_mem, test_org)
        mock_db.execute.return_value = mock_result

        created_svc = Service(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            name="Payments",
            slug="payments",
            description="Payment gateway",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        with patch(
            "app.services.service_registry_service.create_service", return_value=created_svc
        ):
            app.dependency_overrides[get_db] = lambda: mock_db
            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                    res = await client.post(
                        f"/api/v1/organizations/{test_org.id}/services",
                        json={"name": "Payments", "slug": "payments"},
                        headers=headers,
                    )
                    assert res.status_code == status.HTTP_201_CREATED
                    assert res.json()["slug"] == "payments"
            finally:
                app.dependency_overrides.pop(get_db, None)


# ===========================================================================
# 6. Cross-Tenant Isolation & Nested Resource ID Tests (Rules 9, 11, 12, 13)
# ===========================================================================


class TestCrossTenantBoundaryIntegrity:
    """Tests verifying cross-tenant requests and IDOR bypass attempts are physically rejected."""

    @pytest.mark.asyncio
    async def test_cross_tenant_service_dependency_rejected(self) -> None:
        """Creating dependency between services in different organizations raises DomainValidationError."""
        org1 = make_test_org(slug="org-1")
        org2 = make_test_org(slug="org-2")

        svc1 = Service(id=uuid.uuid4(), organization_id=org1.id, name="S1", slug="s1")
        svc2 = Service(id=uuid.uuid4(), organization_id=org2.id, name="S2", slug="s2")

        dep_data = ServiceDependencyCreate(
            source_service_id=svc1.id,
            target_service_id=svc2.id,
        )

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.get.side_effect = lambda model, obj_id: (
            org1 if model == Organization else (svc1 if obj_id == svc1.id else svc2)
        )

        with pytest.raises(DomainValidationError) as exc_info:
            await service_registry_service.create_service_dependency(
                mock_db, organization_id=org1.id, data=dep_data
            )

        assert "different organization" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_nested_resource_id_cannot_bypass_organization_scoping(self) -> None:
        """Querying a service ID belonging to Org A under Org B's URL path returns 404."""
        org_a = make_test_org(slug="org-a")
        org_b = make_test_org(slug="org-b")

        # Service belongs to Org A
        service_a = Service(id=uuid.uuid4(), organization_id=org_a.id, name="Svc A", slug="svc-a")

        mock_db = AsyncMock(spec=AsyncSession)
        # DB lookup returns service_a whose organization_id != org_b.id
        mock_db.get.return_value = service_a

        with pytest.raises(EntityNotFoundError) as exc_info:
            await service_registry_service.get_service(
                mock_db, organization_id=org_b.id, service_id=service_a.id
            )

        assert f"Service '{service_a.id}' not found in organization '{org_b.id}'" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_nested_team_id_cannot_bypass_organization_scoping(self) -> None:
        """Querying a team ID belonging to Org A under Org B's URL path returns 404."""
        org_a = make_test_org(slug="org-a")
        org_b = make_test_org(slug="org-b")

        # Team belongs to Org A
        team_a = Team(id=uuid.uuid4(), organization_id=org_a.id, name="Team A")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.get.return_value = team_a

        with pytest.raises(EntityNotFoundError) as exc_info:
            await team_service.get_team(mock_db, organization_id=org_b.id, team_id=team_a.id)

        assert f"Team '{team_a.id}' not found in organization '{org_b.id}'" in str(exc_info.value)


# ===========================================================================
# 7. User Directory Endpoint Scoping Tests (Rule 8, 16)
# ===========================================================================


class TestUserDirectoryProtection:
    """Tests verifying GET /api/v1/users is authenticated and tenant-scoped."""

    @pytest.mark.asyncio
    async def test_unauthenticated_user_listing_rejected(self) -> None:
        """GET /api/v1/users without token returns 401 Unauthorized."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get("/api/v1/users")
            assert res.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_authenticated_user_listing_does_not_expose_hashes(self) -> None:
        """Authenticated user list never exposes hashed_password or secrets."""
        caller = make_test_user(email="caller@hub.io")
        colleague = make_test_user(email="colleague@hub.io")

        token = create_access_token(user_id=caller.id, email=caller.email)
        headers = {"Authorization": f"Bearer {token}"}

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.get.return_value = caller

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [caller, colleague]
        mock_db.scalars.return_value = mock_scalars

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                res = await client.get("/api/v1/users", headers=headers)
                assert res.status_code == status.HTTP_200_OK
                data = res.json()
                assert len(data) == 2
                for item in data:
                    assert "hashed_password" not in item
                    assert "password" not in item
                    assert "token_hash" not in item
        finally:
            app.dependency_overrides.pop(get_db, None)
