# ADR 003: Authentication and Multi-Tenant Authorization Architecture

## Status
Proposed

## Context
In Milestone 2 (ADR-002), IncidentHub established its core relational domain foundation in PostgreSQL: Organizations, Users, OrganizationMemberships, Teams, TeamMemberships, Services, and ServiceDependencies. The relational multi-tenancy model anchored all tenant resources to an `organization_id` foreign key and enforced database-level boundary integrity for directed service dependencies.

However, Milestone 2 intentionally omitted authentication and authorization. In the current codebase:
- All API endpoints are unauthenticated and accessible to any network caller.
- The `User` model lacks credential storage (no password hash column).
- Resource access in `/api/v1/organizations/{organization_id}/*` relies on client-supplied URL path parameters without verifying that the caller belongs to that organization.
- Unauthenticated callers can list all platform users (`GET /api/v1/users`) or assign arbitrary roles to members (`POST /api/v1/organizations/{id}/members`).

Milestone 3 must establish a production-grade, secure, multi-tenant authentication and authorization architecture without compromising the modular monolith design or adding unnecessary external infrastructure.

Key architectural questions addressed:
1. **Password Hashing Standard**: Which algorithm provides maximum security against modern offline attacks while maintaining high reliability in Python 3.12+?
2. **Token Strategy**: Should the system use stateful server-side sessions, single long-lived JWTs, or a dual-token access/refresh strategy?
3. **Token Scope vs. Tenant Context**: Should access tokens be minted for a specific organization, or should tokens represent global user identity with dynamic organization context resolution?
4. **Authorization Enforcement**: How should organization membership and role permissions be verified in FastAPI without duplicating boilerplate across route handlers?
5. **Information Leakage Prevention**: How should unauthorized access to existing tenant resources be reported without leaking the existence of sensitive organization IDs?

---

## Decisions

### 1. Password Hashing via Argon2id (`pwdlib`)
We decide to adopt **Argon2id** as the sole password hashing algorithm:
- **Cryptographic Strength**: Argon2id is the winner of the Password Hashing Competition (PHC) and is the primary algorithm recommended by OWASP for password storage due to its resistance to both GPU/ASIC cracking and side-channel cache attacks.
- **Library Selection**: We select `pwdlib[argon2]`. We explicitly reject `passlib` because it is unmaintained, deprecated, and triggers runtime warnings and compatibility failures on modern Python releases (3.12+).
- **Password Complexity**: Enforce minimum 10 characters with mixed-case, numeric, and symbolic requirements, capped at 128 characters to prevent denial-of-service via hashing overhead.

### 2. Dual-Token Architecture with Database-Backed Refresh Tokens
We decide to implement a **Dual-Token JWT + Database Refresh Token** model:
- **Access Tokens**: Short-lived (15 minutes), stateless JWTs signed with **HS256** using a high-entropy secret (`JWT_SECRET_KEY`). Signed claims include `sub` (user UUID), `email`, `type: "access"`, `exp`, `iat`, and `jti`.
- **Stateless Verification**: Protected endpoints verify access tokens locally without querying the database for token state, keeping latency low. However, active user status (`user.is_active`) is verified on DB lookup.
- **Refresh Tokens**: Long-lived (7 days), persisted in a dedicated `refresh_tokens` PostgreSQL table.
- **Token Rotation & Reuse Detection**: Every refresh request atomically revokes the presented refresh token and issues a new token pair. If an already-revoked refresh token is replayed, the system detects a potential breach and immediately revokes all active refresh tokens for that user session.
- **Explicit Logout**: Revokes the refresh token in the database, immediately terminating the ability to generate new access tokens.

### 3. Global User Identity Tokens with Per-Request Tenant Context
We decide that JWT access tokens represent **Global Platform User Identity**, not a single organization scope:
- **Rationale**: In IncidentHub, a responder or team lead frequently belongs to multiple organizations. Baking `organization_id` into the access token would force users to re-authenticate or re-issue tokens whenever switching between organizations.
- **Request Context**: Tenant scoping remains anchored to the URL path: `/api/v1/organizations/{organization_id}/...`.
- **Dynamic Context Verification**: For every request targeting an organization, a reusable FastAPI dependency resolves the user's active membership and role in that organization from the database.

### 4. Declarative FastAPI Authorization Dependencies
We decide to encapsulate multi-tenant authorization into two layered FastAPI dependencies:
1. `get_organization_context`: Verifies that `current_user` has an active `OrganizationMembership` in `{organization_id}`. Injects an `OrganizationContext` value object (organization, user, role) into the route handler.
2. `require_org_role(*allowed_roles)`: Evaluates whether the resolved membership role satisfies the required permission level (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`).

### 5. Uniform 404 Not Found for Cross-Tenant Access Attempts
We decide that attempting to access an organization where the authenticated user is not an active member MUST return **HTTP 404 Not Found**, identical to a request for a non-existent organization UUID:
- **Security Rationale**: Returning HTTP 403 Forbidden informs an unauthorized actor that an organization with that UUID exists. Returning 404 prevents tenant enumeration and resource existence probing.
- **Consistency**: This decision extends the Milestone 2 precedent in `get_service()`, which raises `EntityNotFoundError` when a service does not belong to the requested organization.

### 6. Automatic Organization Ownership
We decide that when an authenticated user creates an organization (`POST /api/v1/organizations`), the backend must atomically insert an `OrganizationMembership` record granting that user the `OWNER` role.

---

## Consequences

### Positive
- **Strong Cryptographic Security**: Argon2id ensures resistance to offline credential theft. Short-lived access tokens (15m) minimize exposure windows.
- **Zero External Infrastructure**: Avoids introducing Redis or external session caches in Milestone 3; PostgreSQL handles refresh tokens and membership queries with sub-millisecond index lookups.
- **Breach Resistance**: Refresh token rotation with reuse detection terminates compromised sessions automatically.
- **Clean Developer Experience**: Declarative `Depends(require_org_role(...))` keeps FastAPI endpoint handlers thin and readable.
- **Strict Tenant Isolation**: Prevents IDOR vulnerabilities and eliminates organization enumeration via uniform 404 responses.

### Negative / Trade-offs
- **Database Query on Authenticated Requests**: While access token JWT validation is stateless, resolving user active status and organization membership requires a indexed database lookup per request. For PostgreSQL with connection pooling, this adds negligible overhead (<1ms) while guaranteeing immediate revocation.
- **Schema Migration Required**: Adding `users.hashed_password` and creating `refresh_tokens` requires an Alembic migration (`Milestone 3`).
- **Dependency Addition**: Requires installing `pwdlib[argon2]`, `pyjwt`, and `python-multipart`.
