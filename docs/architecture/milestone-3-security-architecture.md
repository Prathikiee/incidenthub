# Milestone 3: Authentication and Multi-Tenant Authorization Security Architecture

**Author / Assigned Owner:** Prathik (Team Lead and Backend Integration)  
**Status:** Proposed Architecture & Baseline Assessment  
**Target Milestone:** Milestone 3  
**Document Version:** 1.0.0  

---

## 1. Executive Summary & Context

Milestone 2 established IncidentHub's foundational relational domain models in PostgreSQL: Organizations, Users, Memberships, Teams, Services, and Service Dependencies. All entities were created with explicit `organization_id` foreign keys, UUID primary keys, and database-level constraints preventing cross-organization dependencies.

However, Milestone 2 intentionally deferred authentication and access control. In the current repository state:
- All `/api/v1` endpoints are completely unauthenticated and public.
- The `User` entity lacks password hashes, credentials, or session tracking.
- Any client can query or mutate any organization's resources by providing or guessing an `organization_id` in the URL path.
- `GET /api/v1/users` publicly exposes all registered users and emails.
- `POST /api/v1/organizations/{id}/members` allows unauthenticated callers to grant any role (`OWNER`, `ADMIN`, etc.) to any user.

The purpose of **Milestone 3** is to transition IncidentHub from an open development prototype into a production-grade, secure, multi-tenant system by implementing:
1. **Authentication & Identity Management**: Secure registration, password hashing, JWT-based access tokens, database-backed refresh tokens with rotation, and account lifecycle management.
2. **Multi-Tenant Authorization & RBAC**: Request organization context resolution, active membership enforcement, role-based access control (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`), Insecure Direct Object Reference (IDOR) prevention, and cross-tenant boundary isolation.

This document establishes the official security architecture, API contracts, invariants, and implementation roadmap.

---

## 2. Project Baseline & Repository State Assessment

A rigorous inspection of the current repository was performed against commit `7d7f5cc` ("feat: establish core domain foundation") and `HEAD` (`54034dd`):

| Area | Verified Current State | Assessment & Milestone 3 Impact |
| :--- | :--- | :--- |
| **Git Working Tree** | Branch `main`, clean tracked files; `incidenthub/` untracked directory present; `experiment.txt` present. | Baseline verified. No changes to user files. |
| **Backend Dependencies** | `fastapi 0.115+`, `pydantic 2.9+`, `sqlalchemy 2.0+`, `asyncpg`, `alembic`. | **Missing crypto/auth packages**: Need `pwdlib[argon2]` (or `argon2-cffi`), `pyjwt`, and `python-multipart`. |
| **User Model (`models/user.py`)** | Fields: `id`, `email`, `display_name`, `is_active`, timestamps. | **No password hash column**. Must add `hashed_password` via Alembic migration. |
| **Membership Model (`models/membership.py`)** | Enum `OrganizationRole` (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`). Unique `(organization_id, user_id)`. | Clean relational foundation. Needs active status or revocation logic; role hierarchy needs enforcement. |
| **API Endpoints (`api/v1/endpoints/`)** | `health.py`, `organizations.py`, `users.py`, `teams.py`, `services.py`. | All endpoints lack `Depends()` for authentication and role authorization. |
| **Core Config (`core/config.py`)** | Pydantic `Settings` with Postgres connection strings and CORS origins. | Needs `JWT_SECRET_KEY`, `JWT_ALGORITHM`, token expiry durations. |
| **Core Exceptions (`core/exceptions.py`)** | `EntityNotFoundError`, `DuplicateEntityError`, `DomainValidationError`. | Needs `AuthenticationError`, `PermissionDeniedError`, `TenantContextMissingError`. |
| **Frontend Client (`frontend/lib/api.ts`)** | `fetchOrganizations`, `fetchUsers`, `checkBackendHealth`. | No token storage, Authorization headers, or 401 refresh interception. |
| **Frontend Tests (`frontend/tests/`)** | `foundation.test.mjs` (3 passing unit tests). | Tests verified passing. Auth tests must be added in Milestone 3. |

---

## 3. Authentication Architecture

### 3.1 Credential Verification & Password Hashing
- **Algorithm Standard**: **Argon2id** (Memory-hard password hashing, winner of the Password Hashing Competition, OWASP recommended).
- **Library Selection**: `pwdlib[argon2]` (modern, active maintenance, native FastAPI compatibility). Avoid `passlib` due to deprecation and compatibility issues on Python 3.12+.
- **Password Policy**:
  - Minimum 10 characters.
  - At least one uppercase letter, one lowercase letter, one digit, and one special symbol.
  - Maximum 128 characters (prevent DoS via bcrypt/argon2 hashing overhead).
- **Storage**: Stored in `users.hashed_password` (`String(255)`). Never exposed in any Pydantic read schema.

### 3.2 Token Architecture: Dual-Token JWT Strategy

```
Client                              FastAPI Backend                          Database
  │                                        │                                    │
  ├─── POST /api/v1/auth/login ───────────>│                                    │
  │    { email, password }                 │─── Verify Argon2id hash ──────────>│
  │                                        │─── Create RefreshToken record ────>│
  │<── 200 OK ─────────────────────────────│                                    │
  │    { access_token, refresh_token }     │                                    │
  │                                        │                                    │
  │─── GET /api/v1/orgs/:id/services ─────>│                                    │
  │    Authorization: Bearer <access_token>│─── Stateless JWT verify (HS256)    │
  │                                        │─── Check user is_active ──────────>│
  │<── 200 OK ─────────────────────────────│                                    │
  │                                        │                                    │
  │─── POST /api/v1/auth/refresh ─────────>│                                    │
  │    { refresh_token }                   │─── Validate & revoke old token ───>│
  │                                        │─── Issue new token pair ──────────>│
  │<── 200 OK (Rotated Pair) ──────────────│                                    │
```

#### Access Token Specifications
- **Format**: Signed JSON Web Token (RFC 7519).
- **Signing Algorithm**: **HS256** (HMAC-SHA256) with a minimum 256-bit cryptographically secure secret (`JWT_SECRET_KEY`).
- **Lifespan**: **15 minutes** (`ACCESS_TOKEN_EXPIRE_MINUTES = 15`). Short lifespan mitigates credential leakage risks.
- **Claims Payload**:
  ```json
  {
    "sub": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "jane@incidenthub.io",
    "type": "access",
    "iat": 1776000000,
    "exp": 1776000900,
    "jti": "b0f7e61a-4720-4e3b-9a8c-9c7a2b91d2ef"
  }
  ```
- **Tenant Scope Decision**: The access token represents the user's global identity (`sub`), **not** a single organization scope. This allows a user to access multiple organizations without requiring constant token re-negotiation. Organization context is established per request.

#### Refresh Token & Rotation Strategy
- **Lifespan**: **7 days** (`REFRESH_TOKEN_EXPIRE_DAYS = 7`).
- **Database Persistence**: Refresh tokens are tracked in a dedicated `refresh_tokens` database table:
  - `id`: UUID Primary Key.
  - `user_id`: UUID Foreign Key referencing `users.id` (CASCADE).
  - `token_hash`: SHA-256 hash of the refresh token secret.
  - `expires_at`: Timestamp with timezone.
  - `revoked_at`: Nullable timestamp with timezone.
  - `created_at`: Timestamp with timezone.
  - `user_agent`: Optional client user-agent string.
- **Token Rotation**: Each refresh request atomically revokes the consumed refresh token and issues a new refresh token and access token.
- **Reuse Detection & Compromise Protection**: If a previously revoked refresh token is presented, the system detects a breach and immediately revokes all active refresh tokens for that user session, forcing full re-authentication.

### 3.3 Current-User Resolution Dependencies

In FastAPI, authentication dependencies are structured hierarchically:

1. `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")`: Extracts Bearer token from the `Authorization` header.
2. `get_current_user_token_payload(token: str = Depends(oauth2_scheme)) -> TokenPayload`:
   - Decodes JWT using `settings.JWT_SECRET_KEY` and `settings.JWT_ALGORITHM`.
   - Validates signature and `exp`.
   - Enforces `payload.type == "access"`.
   - Raises HTTP 401 with `WWW-Authenticate: Bearer` on any validation failure.
3. `get_current_active_user(payload: TokenPayload = Depends(...), db: AsyncSession = Depends(get_db)) -> User`:
   - Retrieves user by `payload.sub` from the database.
   - Verifies `user.is_active is True`.
   - Raises HTTP 401 if user does not exist or has been disabled.

---

## 4. Multi-Tenant Authorization Architecture

### 4.1 Organization Context Resolution

All tenant-scoped endpoints follow the established URI structure:
`/api/v1/organizations/{organization_id}/...`

Tenant context resolution is encapsulated in a reusable FastAPI dependency:

```python
async def get_organization_context(
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationContext:
    """Resolve and verify active organization context for the authenticated user."""
```

The `OrganizationContext` value object encapsulates:
- `organization`: The verified `Organization` model instance.
- `user`: The authenticated `User` model instance.
- `role`: The user's resolved `OrganizationRole` (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`).

### 4.2 Membership Verification & Information Leakage Prevention

When an authenticated user requests an organization resource (`/api/v1/organizations/{organization_id}/...`):
1. The dependency queries `OrganizationMembership` for `(organization_id, current_user.id)`.
2. **If membership does not exist**:
   - The dependency raises `HTTP 404 Not Found` with message `"Organization not found"`.
   - **Critical Security Rationale**: Returning HTTP 403 would leak to an attacker that an organization with that UUID actually exists. Returning 404 ensures uniform behavior between non-existent organizations and unauthorized organizations, preventing organization enumeration.
3. **If membership exists**: The user's role is extracted, and the request proceeds to permission evaluation.

### 4.3 Role-Based Access Control (RBAC) Matrix

IncidentHub defines four hierarchical roles within each organization:

| Capability / Resource Action | VIEWER | MEMBER | ADMIN | OWNER |
| :--- | :---: | :---: | :---: | :---: |
| **Read Organization Details** | Yes | Yes | Yes | Yes |
| **Update Organization (Name/Slug)** | No | No | Yes | Yes |
| **Delete Organization** | No | No | No | Yes |
| **List Services & Dependencies** | Yes | Yes | Yes | Yes |
| **Register / Update Service** | No | Yes | Yes | Yes |
| **Declare Service Dependency** | No | Yes | Yes | Yes |
| **Delete Service / Dependency** | No | No | Yes | Yes |
| **View Teams & Team Members** | Yes | Yes | Yes | Yes |
| **Create / Modify Team** | No | No | Yes | Yes |
| **Assign User to Team** | No | No | Yes | Yes |
| **List Organization Members** | Yes | Yes | Yes | Yes |
| **Invite / Add Member (MEMBER/VIEWER)** | No | No | Yes | Yes |
| **Promote Member to ADMIN** | No | No | No | Yes |
| **Remove Member** | No | No | Yes (non-owners) | Yes |
| **Transfer Ownership** | No | No | No | Yes |

#### Declarative Role Enforcement in Routes
Route handlers declare role requirements using parameterized dependency factories:

```python
def require_org_role(*allowed_roles: OrganizationRole):
    async def role_checker(
        ctx: OrganizationContext = Depends(get_organization_context),
    ) -> OrganizationContext:
        if ctx.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this organization operation",
            )
        return ctx
    return role_checker
```

### 4.4 Insecure Direct Object Reference (IDOR) Prevention

To prevent cross-tenant data leakage:
1. **Mandatory Compound Scoping**: Every database read, update, or delete on tenant-scoped tables must explicitly include `organization_id` in the query filter:
   ```python
   # Correct IDOR-safe query:
   stmt = select(Service).where(
       Service.id == service_id,
       Service.organization_id == organization_id,
   )
   ```
2. **Database Engine Safeguards**:
   - As established in ADR-002, `services` has a composite unique constraint on `(id, organization_id)`.
   - `service_dependencies` enforces composite foreign keys `(source_service_id, organization_id)` and `(target_service_id, organization_id)`.
   - Even if application code were compromised, PostgreSQL physically rejects any dependency edge crossing organization boundaries.

---

## 5. Security Invariants & Threat Scenarios

The following invariants MUST be verified by automated unit, integration, and security tests:

1. **Unauthenticated Denial**: Any request to protected endpoints without a valid `Authorization: Bearer <token>` header receives `HTTP 401 Unauthorized`.
2. **Tenant Boundary Isolation**: A user with valid credentials in Organization A attempting to read or mutate resources in Organization B receives `HTTP 404 Not Found`.
3. **No Self-Elevation**: A user cannot modify their own `OrganizationMembership.role` through membership endpoints. Only an `OWNER` can modify `ADMIN` or `OWNER` roles.
4. **Immediate Deactivation Effect**: When `user.is_active` is set to `False`, all subsequent requests by that user fail with `HTTP 401 Unauthorized`, even if their JWT access token has not yet expired.
5. **Cryptographic Integrity**: Tokens with modified signatures, unsupported algorithms (`alg=none`), expired timestamps, or invalid token types (`type=refresh` presented as access token) fail validation.
6. **Zero-Log Invariant**: Passwords, password hashes, JWT signatures, and Bearer tokens must never appear in application log streams, exception stack traces, or client error payloads.
7. **Public Boundary Preservation**: `/health` and `/api/v1/health` remain unconditionally unauthenticated.
8. **Ownership Preservation**: An organization must have at least one active `OWNER`. An `OWNER` cannot leave or downgrade their role without transferring ownership to another member.

---

## 6. Proposed API Contracts

*All endpoints in this section are architectural proposals for Milestone 3 implementation.*

### 6.1 Authentication Endpoints (`/api/v1/auth`)

#### `POST /api/v1/auth/register`
- **Summary**: Register a new platform user.
- **Auth Required**: None (Public).
- **Request Body**:
  ```json
  {
    "email": "responder@incidenthub.io",
    "password": "StrongPassword123!",
    "display_name": "Alex Vance"
  }
  ```
- **Responses**:
  - `201 Created`: Returns `UserRead` schema.
  - `400 Bad Request`: Password fails complexity rules or email malformed.
  - `409 Conflict`: Email already registered.

#### `POST /api/v1/auth/login`
- **Summary**: Authenticate credentials and receive token pair.
- **Auth Required**: None (Public).
- **Request Body**:
  ```json
  {
    "email": "responder@incidenthub.io",
    "password": "StrongPassword123!"
  }
  ```
- **Responses**:
  - `200 OK`:
    ```json
    {
      "access_token": "eyJhbGciOi...",
      "refresh_token": "eyJhbGciOi...",
      "token_type": "bearer",
      "expires_in": 900,
      "user": {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "email": "responder@incidenthub.io",
        "display_name": "Alex Vance"
      }
    }
    ```
  - `401 Unauthorized`: Invalid email or password.
  - `403 Forbidden`: User account is deactivated (`is_active=False`).

#### `POST /api/v1/auth/refresh`
- **Summary**: Exchange refresh token for a new token pair.
- **Auth Required**: None (Refresh Token in body).
- **Request Body**:
  ```json
  {
    "refresh_token": "eyJhbGciOi..."
  }
  ```
- **Responses**:
  - `200 OK`: Returns new `access_token` and rotated `refresh_token`.
  - `401 Unauthorized`: Token expired, revoked, or invalid.

#### `POST /api/v1/auth/logout`
- **Summary**: Revoke active refresh token.
- **Auth Required**: `Bearer <access_token>`.
- **Request Body**:
  ```json
  {
    "refresh_token": "eyJhbGciOi..."
  }
  ```
- **Responses**:
  - `204 No Content`: Refresh token successfully revoked.
  - `401 Unauthorized`: Invalid access token.

#### `GET /api/v1/auth/me`
- **Summary**: Retrieve profile and organization memberships of current user.
- **Auth Required**: `Bearer <access_token>`.
- **Responses**:
  - `200 OK`:
    ```json
    {
      "user": {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "email": "responder@incidenthub.io",
        "display_name": "Alex Vance",
        "is_active": true
      },
      "memberships": [
        {
          "organization_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
          "organization_name": "Acme Corp",
          "organization_slug": "acme-corp",
          "role": "ADMIN"
        }
      ]
    }
    ```

---

### 6.2 Updated Existing Endpoints

| Method | Endpoint | Auth | Required Org Role | Behavior Change from Milestone 2 |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/organizations` | Yes | N/A | **Filtered**: Returns only organizations where `current_user` has active membership. |
| `POST` | `/api/v1/organizations` | Yes | N/A | **Auto-Owner**: Creates organization and automatically creates `OrganizationMembership` assigning `current_user` as `OWNER`. |
| `GET` | `/api/v1/organizations/{id}` | Yes | Any Member | Rejects non-members with `404 Not Found`. |
| `POST` | `/api/v1/organizations/{id}/members` | Yes | `ADMIN`, `OWNER` | Rejects non-admins with `403 Forbidden`. Only `OWNER` can assign `ADMIN` or `OWNER`. |
| `GET` | `/api/v1/organizations/{id}/members` | Yes | Any Member | Rejects non-members with `404 Not Found`. |
| `POST` | `/api/v1/organizations/{id}/services` | Yes | `MEMBER`, `ADMIN`, `OWNER` | Rejects `VIEWER` with `403 Forbidden`. |
| `POST` | `/api/v1/organizations/{id}/teams` | Yes | `ADMIN`, `OWNER` | Rejects `MEMBER` and `VIEWER` with `403 Forbidden`. |
| `GET` | `/api/v1/users` | Yes | Admin / Internal | **Restricted**: Replaced with user lookup or scoped to organization members. |

---

## 7. Frontend Session Architecture

1. **Token Storage**:
   - Access token stored in memory (React context / state management).
   - Refresh token stored in `httpOnly`, `Secure`, `SameSite=Lax` cookie OR secure web storage.
2. **HTTP Interceptor (`frontend/lib/api.ts`)**:
   - Injects `Authorization: Bearer <access_token>` into outbound requests.
   - On receiving `HTTP 401 Unauthorized`:
     - Pauses pending requests.
     - Calls `/api/v1/auth/refresh`.
     - Retries original request with new token.
     - If refresh fails, clears session state and redirects user to `/login`.
3. **Route Protection**:
   - Next.js middleware protects `/dashboard`, `/organizations`, and workspace routes.
   - Public routes: `/login`, `/register`, `/health`.

---

## 8. Database Schema Modifications (Milestone 3 Migration Plan)

Milestone 3 requires a single, cohesive, reversible Alembic migration:

1. **`users` Table Update**:
   - Add column `hashed_password` (`String(255)`, `nullable=False`).
   - For existing test records (if any), a default hash or nullable transitional state is used.
2. **New `refresh_tokens` Table**:
   - `id`: UUID Primary Key.
   - `user_id`: UUID Foreign Key referencing `users.id` (ondelete="CASCADE").
   - `token_hash`: String(64) indexed (SHA-256 of token secret).
   - `expires_at`: DateTime(timezone=True) nullable=False.
   - `revoked_at`: DateTime(timezone=True) nullable=True.
   - `created_at`: DateTime(timezone=True) server_default=func.now().
   - `user_agent`: String(500) nullable=True.
   - Index on `(user_id, token_hash)`.

---

## 9. Conclusion & Architecture Approval

This architecture maintains IncidentHub's modular monolith principles, introduces zero unnecessary infrastructure, provides cryptographic and multi-tenant security guarantees, and sets clear contracts for team execution.
