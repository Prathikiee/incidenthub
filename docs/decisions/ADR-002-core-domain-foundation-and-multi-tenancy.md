# ADR 002: Core Domain Foundation and Multi-Tenant Relational Model

## Status
Accepted

## Context
IncidentHub is designed to reconstruct operational incidents as temporal evidence stories. To reason about an incident, the system must know *what* was impacted (services and systems), *who* responded (users, teams, and memberships), and *how* components interact (service dependencies).

Before introducing dynamic incidents, timeline event streams, or AI-assisted investigation, the system must establish a sound, relational domain foundation.

Key design challenges addressed:
1. **Multi-Tenancy & Isolation**: Preventing cross-tenant data leaks and accidental cross-organization relationships.
2. **Graph Structure vs. Database Engine**: Determining whether to introduce a dedicated graph database or leverage PostgreSQL as the relational source of truth.
3. **Graph Topology Integrity**: Ensuring directed service dependencies cannot cross tenant boundaries or form self-referential loops.

## Decisions

### 1. PostgreSQL as the Single Source of Truth
We explicitly decide **not** to introduce a separate graph database (e.g., Neo4j) or NoSQL document store.
- **Relational Integrity**: Operational entities (Organizations, Users, Teams, Services) naturally form relational hierarchies.
- **ACID Guarantees**: Incidents and evidence require strict transactional consistency across services and teams.
- **Graph Capabilities**: Directed service dependency graphs and incident causal chains can be modeled with standard relational foreign keys, composite constraints, and recursive Common Table Expressions (`WITH RECURSIVE`) without distributed database overhead.
- **pgvector & JSONB**: PostgreSQL natively supports vector embeddings and unstructured telemetry payloads for subsequent milestones.

### 2. Multi-Tenant Architectural Model
The primary tenant boundary is the **Organization**:
- Every operational resource (`Team`, `Service`, `ServiceDependency`, `OrganizationMembership`) contains an explicit `organization_id` foreign key.
- Primary keys are UUIDs across all entities.
- Users represent actors who can belong to multiple organizations via `OrganizationMembership` with explicit roles (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`).
- Users must belong to an organization before joining any team within that organization.

### 3. Service Dependency Model with Database-Level Tenant Guarantees
A service dependency represents a directed relationship: `source_service_id` depends on `target_service_id` (e.g., Checkout API depends on Payment Service).

To prevent cross-tenant dependencies:
1. `services` defines a composite unique constraint on `(id, organization_id)`.
2. `service_dependencies` defines composite foreign keys:
   - `FOREIGN KEY (source_service_id, organization_id) REFERENCES services(id, organization_id)`
   - `FOREIGN KEY (target_service_id, organization_id) REFERENCES services(id, organization_id)`
3. At the database level, PostgreSQL mathematically guarantees that `source_service_id` and `target_service_id` share the exact same `organization_id`.
4. Self-dependency is prevented via a database check constraint (`source_service_id != target_service_id`) and validated in the application layer.
5. Duplicate dependency edges are rejected via unique constraint on `(source_service_id, target_service_id)`.

### 4. Preparation for the Future Temporal Incident Graph
The entities established in Milestone 2 form the structural anchor for subsequent incident intelligence:
- **Temporal System Graph**: `Service` entities represent graph nodes; `ServiceDependency` entities represent graph edges. In future milestones, time-versioned state changes (e.g., deployments, config updates) will attach directly to these nodes.
- **Incident Stories**: An incident will link to the affected `Service` and owning `Team`, enabling automated blast-radius calculation and causal graph traversal.
- **Evidence & Hypotheses**: Responders will attach telemetry evidence and formulate hypotheses pointing to specific services in the dependency graph.

## Consequences

### Positive
- Strict, database-enforced multi-tenancy preventing data cross-contamination.
- Zero extra operational infrastructure (no external graph DB or sync pipelines).
- Clean SQLAlchemy 2.x declarative models and Pydantic v2 validation schemas.
- Reversible Alembic migrations with clean PostgreSQL enum lifecycle handling.
- Service-layer encapsulation keeping FastAPI route handlers thin.

### Negative / Trade-offs
- Deep multi-hop graph path queries require recursive SQL CTEs rather than Cypher graph queries. For operational service graphs (typically dozens to thousands of services per org), PostgreSQL recursive CTEs perform with sub-millisecond latencies.
