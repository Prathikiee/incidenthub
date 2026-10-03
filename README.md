# IncidentHub

> **Temporal incident intelligence and response workspace for reconstructing operational incidents through timelines, evidence graphs, system state, and responder decisions.**

IncidentHub shifts the incident response paradigm from superficial ticket tracking (status updates, severity labels, chat logs) to **temporal evidence stories**. By capturing the full causal journey—what happened, what the system state looked like, what evidence was discovered, what hypotheses responders considered, and what consequences followed each mitigation action—IncidentHub enables teams to reason during crises and deterministically reconstruct incidents afterward.

---

## Current Status: Milestone 1 (Foundation)

Milestone 1 establishes the repository architecture foundation, core service skeletons, quality tooling, database connectivity, and containerized development infrastructure.

| Area | Milestone 1 Foundation | Status | Planned for Later Milestones |
| :--- | :--- | :--- | :--- |
| **Architecture** | Modular Monolith (Clear Boundaries) | Ready | Asynchronous workers, event-driven pipelines |
| **Frontend** | Next.js (App Router), React 19, TypeScript, Tailwind CSS | Ready | shadcn/ui, TanStack Query, Zustand, React Flow |
| **Backend** | FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic | Ready | Domain entities, Celery tasks, WebSockets |
| **Database** | PostgreSQL 16 connection pool & Alembic migration plumbing | Ready | pgvector, incident schema, evidence tables |
| **Orchestration**| Docker Compose (frontend, backend, postgres) | Ready | Redis, Prometheus, Grafana, OpenTelemetry |
| **Code Quality** | Ruff, MyPy, ESLint, Prettier, Pytest, Node Test Runner | Ready | Vitest, Playwright, CI release automation |

---

## Repository Structure

```
incidenthub/
├── .github/
│   └── workflows/
│       └── ci.yml               # Automated CI for lint, type checks, tests, and build
├── backend/
│   ├── alembic/                 # Database migration scripts and configuration
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/              # Versioned API routes (/api/v1)
│   │   ├── core/                # Application settings and Pydantic configuration
│   │   ├── db/                  # SQLAlchemy 2.x DeclarativeBase and asyncpg session
│   │   ├── models/              # Database models (domain models planned for M2)
│   │   ├── schemas/             # Pydantic validation schemas
│   │   ├── services/            # Domain business logic services
│   │   └── main.py              # FastAPI entrypoint (/health, CORS, /api/v1 router)
│   ├── tests/                   # Pytest test suite (health checks, client fixtures)
│   ├── pyproject.toml           # Backend dependencies, Ruff, MyPy, and Pytest config
│   └── .env.example             # Backend environment template
├── frontend/
│   ├── app/                     # Next.js App Router (layout.tsx, page.tsx, globals.css)
│   ├── components/              # Reusable UI components (BackendStatus, Header, etc.)
│   ├── lib/                     # API client utilities and health probe helpers
│   ├── public/                  # Static assets
│   ├── tests/                   # Frontend foundation tests
│   ├── package.json             # Next.js scripts and dependencies
│   ├── tsconfig.json            # TypeScript configuration
│   └── .env.example             # Frontend environment template
├── docs/
│   ├── architecture/
│   │   └── system-architecture.md   # Architectural design, boundaries, and roadmap
│   └── decisions/
│       └── ADR-001-modular-monolith-foundation.md # Foundational architectural decision
├── infrastructure/
│   └── docker/
│       ├── backend.Dockerfile   # Python 3.12-slim development image
│       └── frontend.Dockerfile  # Node 24-alpine development image
├── .env.example                 # Root environment variables template
├── .gitignore                   # Multi-language root ignore rules
├── docker-compose.yml           # Local multi-service development compose
├── LICENSE                      # MIT License
└── README.md                    # Project documentation
```

---

## Getting Started: Local Development

You can run IncidentHub either using **Docker Compose** (recommended for full environment parity) or **independently** on your host machine.

### Option A: Docker Compose (All Services)

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
   docker compose up --build
   ```

4. **Access the services**:
   - **Frontend UI**: [http://localhost:3000](http://localhost:3000)
   - **Backend API**: [http://localhost:8000](http://localhost:8000)
   - **Backend Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
   - **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **PostgreSQL**: `localhost:5432` (`user: postgres`, `db: incidenthub`)

---

### Option B: Running Services Independently

#### 1. Backend Service (FastAPI)

Prerequisites: Python 3.11+ (Python 3.12 recommended).

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate

# Install dependencies in editable mode with development tools
pip install -e ".[dev]"

# (Optional) Copy environment template
cp .env.example .env

# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```

Verify backend health:
```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

#### 2. Frontend Application (Next.js)

Prerequisites: Node.js 20+ (Node.js 24 recommended).

```bash
cd frontend

# Install dependencies
npm ci

# (Optional) Copy environment template
cp .env.example .env.local

# Start Next.js development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Testing & Quality Assurance

Both frontend and backend include automated linting, type-checking, and test verification.

### Backend Verification

```bash
cd backend

# Run unit tests
pytest

# Run Ruff linter and formatter checks
ruff check .
ruff format --check .

# Run static type checking
mypy app
```

### Frontend Verification

```bash
cd frontend

# Run unit / foundation tests
npm test

# Run ESLint
npm run lint

# Run Prettier code formatting check
npm run format:check

# Compile production build
npm run build
```

---

## Security Principles

- **Zero Committed Secrets**: All secrets and credentials are managed via environment variables. `.env.example` templates contain only non-secret placeholders.
- **Backend Authorization Authority**: The backend is the sole source of truth for business logic, validation, and access control.
- **Tenant Isolation Readiness**: The modular monolith foundation is architected for clean tenant boundaries and role-based access control (RBAC).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
