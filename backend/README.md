# IncidentHub Backend

FastAPI backend service for IncidentHub - temporal incident intelligence and response workspace.

## Milestone 1: Architecture Foundation

This service provides the core application foundation, database connection management (SQLAlchemy 2.x + Alembic), versioned API routing (`/api/v1`), and operational health monitoring (`/health`).

## Quickstart

### Prerequisites
- Python 3.11+
- Virtual environment (`.venv`)

### Installation

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install dependencies with development extras
pip install -e ".[dev]"
```

### Running Locally

```bash
uvicorn app.main:app --reload --port 8000
```

### Running Tests

```bash
pytest
```

### Linting and Type Checking

```bash
ruff check .
mypy app
```
