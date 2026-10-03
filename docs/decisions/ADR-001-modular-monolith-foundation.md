# ADR 001: Modular Monolith Repository and Architecture Foundation

## Status
Accepted

## Context
IncidentHub is an incident intelligence and response workspace designed to reconstruct operational incidents as temporal evidence stories. Responders need to correlate timelines, system state, evidence graphs, hypotheses, actions, and post-action consequences.

Establishing a new system carries risks of premature distribution (e.g. microservices sprawl, complex distributed state, unnecessary queue layers) before core domain models and workflows are stabilized.

## Decision

1. **Architecture Style**: Adopt a **Modular Monolith** pattern.
   - Maintain clear separation between Frontend (`/frontend`), Backend (`/backend`), and Infrastructure (`/infrastructure`).
   - Keep business logic centralized in the FastAPI backend rather than splitting into multiple microservices.
   - Postpone distributed queues (Celery/Redis) and vector stores (pgvector) until domain requirements in subsequent milestones demand them.

2. **Frontend Stack**:
   - **Next.js (App Router) + React + TypeScript**: Standardizes modern server/client rendering and typed component trees.
   - **Tailwind CSS**: Provides utility-first styling without runtime overhead.
   - shadcn/ui, TanStack Query, Zustand, and React Flow are scheduled for subsequent milestones when domain models and interactive canvas workflows are introduced.

3. **Backend Stack**:
   - **FastAPI**: High performance asynchronous web framework with native OpenAPI documentation.
   - **Pydantic v2**: Strict, typed schema validation and configuration management (`pydantic-settings`).
   - **SQLAlchemy 2.x + Asyncpg**: Modern async ORM foundation for high-throughput I/O.
   - **Alembic**: Database schema migration engine connected to SQLAlchemy `DeclarativeBase`.

4. **Database Strategy**:
   - **PostgreSQL**: Industry standard relational engine capable of supporting transactional incident records, JSON payloads, and relational graphs.
   - Milestone 1 strictly introduces connection and migration plumbing without inventing unverified domain tables.

5. **API Design & Versioning**:
   - Versioned API router namespace `/api/v1` for all future domain resources.
   - Standard unversioned `/health` endpoint returning `{"status": "ok"}` for orchestration and liveness checks.

## Consequences

### Positive
- Rapid development velocity with zero distributed orchestration friction.
- Straightforward local setup for developers via single Docker Compose or independent processes.
- Clear module boundaries prevent coupling while keeping deployment simple.
- Strict typing across Python (MyPy) and TypeScript ensures interface consistency.

### Negative / Trade-offs
- Features requiring asynchronous workers or background telemetry ingestion must be introduced in planned milestones rather than day one.
