# IncidentHub

> **Temporal incident intelligence and response workspace for reconstructing operational incidents through timelines, evidence graphs, system state, and responder decisions.**

IncidentHub shifts the incident response paradigm from superficial ticket tracking (status updates, severity labels, chat logs) to **temporal evidence stories**. By capturing the full causal journey—what happened, what the system state looked like, what evidence was discovered, what hypotheses responders considered, and what consequences followed each mitigation action—IncidentHub enables teams to reason during crises and deterministically reconstruct incidents afterward.

---

## Current Status: Milestone 2 (Core Domain Foundation)

Milestone 2 establishes the foundational relational domain model and multi-tenant schema in PostgreSQL, supported by SQLAlchemy 2.x, Alembic, Pydantic v2 schemas, thin FastAPI endpoints, and service-layer encapsulation.

| Area | Milestone 2 Foundation | Status | Planned for Later Milestones |
| :--- | :--- | :--- | :--- |
| **Domain Model** | Organizations, Users, Memberships, Teams, Services, Dependencies | **Ready** | Incidents, Timelines, Hypotheses, Decisions, Evidence |
| **Multi-Tenancy** | Organization-scoped isolation & composite foreign keys | **Ready** | Auth-token tenant guards, scoped RBAC claims |
| **Service Graph** | Directed service dependencies with DB-level tenant enforcement | **Ready** | Temporal graph versioning, React Flow canvas |
| **Migrations** | Alembic migration `39ae0ff14533` (tested upgrade/downgrade) | **Ready** | Incremental incident tables & indices |
| **Backend API** | Versioned REST endpoints under `/api/v1` with validation | **Ready** | Authentication (JWT/OAuth), WebSockets |
| **Frontend** | Domain foundation status component & typed API client | **Ready** | Incident dashboard, interactive canvas |
| **Quality** | Ruff, MyPy (strict), Pytest (28 tests), ESLint, Prettier | **Passing** | Integration test coverage, Playwright |

---

## Core Domain Model

PostgreSQL serves as the single source of truth for all operational entities and topologies:

```
Organization (Tenant Boundary)
  ├── OrganizationMembership (OWNER, ADMIN, MEMBER, VIEWER)
  │     └── User (Email, Display Name)
  ├── Team (Squad / Grouping)
  │     └── TeamMembership (Organization-verified User)
  ├── Service (Software Component / Microservice)
  └── ServiceDependency (Directed Graph Edge: Source -> Target)
```

### Relational & Multi-Tenant Guarantees
- **Tenant Isolation**: All tenant resources reference `organization_id` with foreign key cascade rules.
- **Service Dependency Integrity**:
  - `source_service_id != target_service_id` enforced by database check constraint.
  - Dependencies cannot cross organizations: guaranteed at the database level via composite foreign keys referencing `services(id, organization_id)`.
  - Duplicate relationships prevented by unique constraints.
- **User Normalization**: User emails are validated, stripped, and normalized to lowercase.
- **Reversible Migrations**: Migration revision `39ae0ff14533` creates all 7 tables and enums, and is verified for reversible downgrade/upgrade.

---

## Repository Structure

```
incidenthub/
├── .github/
│   └── workflows/
│       └── ci.yml               # Automated CI for lint, type checks, tests, and build
├── backend/
│   ├── alembic/                 # Database migrations (env.py, versions/)
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/              # Versioned API routes (orgs, users, teams, services)
│   │   ├── core/                # Settings and domain exceptions
│   │   ├── db/                  # Base DeclarativeBase and async session factory
│   │   ├── models/              # SQLAlchemy 2.x declarative models
│   │   ├── schemas/             # Pydantic v2 validation schemas
│   │   ├── services/            # Domain service logic (organization, user, team, service)
│   │   └── main.py              # FastAPI entrypoint, exception handlers, and CORS
│   ├── tests/                   # Pytest suite (health, orgs, users, teams, services, migrations)
│   ├── pyproject.toml           # Backend dependencies, Ruff, MyPy, and Pytest config
│   └── .env.example             # Backend environment template
├── frontend/
│   ├── app/                     # Next.js App Router (layout.tsx, page.tsx, globals.css)
│   ├── components/              # UI components (BackendStatus, DomainFoundationStatus)
│   ├── lib/                     # Typed API client (organizations, users, status)
│   ├── public/                  # Static assets
│   ├── tests/                   # Frontend unit tests
│   ├── package.json             # Next.js scripts and dependencies
│   ├── tsconfig.json            # TypeScript configuration
│   └── .env.example             # Frontend environment template
├── docs/
│   ├── architecture/
│   │   └── system-architecture.md   # System architecture, ER diagram, roadmap
│   └── decisions/
│       ├── ADR-001-modular-monolith-foundation.md
│       └── ADR-002-core-domain-foundation-and-multi-tenancy.md
├── infrastructure/
│   └── docker/
│       ├── backend.Dockerfile   # Python 3.12-slim development image
│       └── frontend.Dockerfile  # Node 24-alpine development image
├── .env.example                 # Root environment variables template
├── .gitignore                   # Multi-language root ignore rules
├── docker-compose.yml           # Multi-container orchestration (postgres, backend, frontend)
├── LICENSE                      # MIT License
└── README.md                    # Project documentation
```

---

## Getting Started: Local Development

### Option A: Docker Compose (Recommended)

1. **Clone the repository and enter the directory**:
   ```bash
   cd incidenthub
   ```

2. **Copy the environment configuration**:
   ```bash
   cp .env.example .env
   ```

3. **Build and start all services**:
   ```bash
   docker compose up --build -d
   ```

4. **Run database migrations inside the backend container**:
   ```bash
   docker compose exec backend alembic upgrade head
   ```

5. **Access the services**:
   - **Frontend UI**: [http://localhost:3000](http://localhost:3000)
   - **Backend API**: [http://localhost:8000](http://localhost:8000)
   - **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **PostgreSQL**: `localhost:5432` (`user: postgres`, `db: incidenthub`)

---

### Option B: Running Services Locally

#### 1. Backend Service (FastAPI)

Prerequisites: Python 3.11+ and running PostgreSQL 16 container.

```bash
cd backend
python -m venv .venv

# On Windows:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend Application (Next.js)

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## API Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service liveness probe |
| `GET` | `/api/v1/health` | Versioned operational health |
| `POST` | `/api/v1/organizations` | Create an organization (unique slug) |
| `GET` | `/api/v1/organizations` | List all organizations |
| `GET` | `/api/v1/organizations/{id}` | Get organization by ID |
| `POST` | `/api/v1/organizations/{id}/members` | Add member to organization |
| `GET` | `/api/v1/organizations/{id}/members` | List organization members |
| `POST` | `/api/v1/users` | Register user (normalized email) |
| `GET` | `/api/v1/users` | List registered users |
| `GET` | `/api/v1/users/{id}` | Get user by ID |
| `POST` | `/api/v1/organizations/{id}/teams` | Create team in organization |
| `GET` | `/api/v1/organizations/{id}/teams` | List teams in organization |
| `GET` | `/api/v1/organizations/{id}/teams/{team_id}` | Get team details |
| `POST` | `/api/v1/organizations/{id}/teams/{team_id}/members` | Assign member to team |
| `GET` | `/api/v1/organizations/{id}/teams/{team_id}/members` | List team members |
| `POST` | `/api/v1/organizations/{id}/services` | Register service in organization |
| `GET` | `/api/v1/organizations/{id}/services` | List organization services |
| `GET` | `/api/v1/organizations/{id}/services/{service_id}` | Get service details |
| `POST` | `/api/v1/organizations/{id}/service-dependencies` | Declare directed dependency |
| `GET` | `/api/v1/organizations/{id}/service-dependencies` | List service dependencies |

---

## Testing & Quality Assurance

### Backend Verification
```bash
cd backend
pytest                                # Run full test suite (28 tests)
ruff check .                          # Linter checks
ruff format --check .                 # Formatter checks
mypy app tests                        # Strict static type checking
```

### Frontend Verification
```bash
cd frontend
npm test                              # Run unit tests
npm run lint                          # Run ESLint
npm run format:check                  # Prettier checks
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
