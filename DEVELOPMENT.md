# Local Development Guide

How to run The-Code Adaptive LMS (`maestronexus`) locally. This complements the
design docs in [docs/](docs/) and the stack decisions in
[docs/18_technical_decisions.md](docs/18_technical_decisions.md).

The local setup uses **native services** (no Docker). The backend is a FastAPI
modular monolith; the frontend is a Next.js app.

## Repository layout

```
maestro/
  backend/     # FastAPI modular monolith (Python 3.12, uv)
  frontend/    # Next.js (App Router, TS, Tailwind, shadcn/ui, React Flow)
  docs/        # Design + planning documentation
  .localdev/   # Local-only: MinIO binaries/data, helper scripts, logs (gitignored)
```

## Prerequisites (installed)

| Tool / service | Version | Notes |
|----------------|---------|-------|
| Git | 2.46 | |
| Node.js + npm | 22.x / 11.x | frontend |
| Python | 3.12 (via uv) + 3.13 system | backend uses 3.12 |
| uv | 0.9.x | Python package/venv manager |
| PostgreSQL | 18.2 | Windows service `postgresql-x64-18`, port 5432 |
| Redis (Memurai) | 4.1.2 | Windows service `Memurai`, port 6379 |
| MinIO | latest | run from `.localdev` (not a service yet) |

> pgvector is **not yet installed** (deferred until AI/RAG features begin).

## Local services

| Service | Endpoint | Credentials (dev only) |
|---------|----------|------------------------|
| PostgreSQL | `localhost:5432` | db `maestronexus`, user `maestro` / `maestro-dev-secret123` |
| Redis (Memurai) | `localhost:6379` | none |
| MinIO API | `http://localhost:9000` | `maestro` / `maestro-dev-secret123` |
| MinIO Console | `http://localhost:9001` | same |

Postgres and Memurai start automatically (Windows services). Start MinIO with:

```powershell
powershell -ExecutionPolicy Bypass -File .localdev\start-minio.ps1
```

## Run the backend

```powershell
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs
- Readiness (checks Postgres + Redis + MinIO): http://localhost:8000/health/ready

## Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

- App: http://localhost:3000 (shows live backend service health)

The frontend reads the backend URL from `frontend/.env.local`
(`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`).

## Typical dev loop

1. Ensure services are up: Postgres + Memurai (auto), MinIO (`start-minio.ps1`).
2. Terminal A: `cd backend && uv run uvicorn app.main:app --reload --port 8000`
3. Terminal B: `cd frontend && npm run dev`
4. Open http://localhost:3000 — the home page should report all three services healthy.

## Database migrations (Alembic)

Models are added under `backend/app/modules/<module>/models.py` and imported in
`backend/migrations/env.py`, then:

```powershell
cd backend
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

## Not yet set up (intentionally)

- pgvector extension (deferred).
- MinIO as an auto-start Windows service (currently launched via script).
- Background worker (Celery/ARQ) — modules are scaffolded; worker process comes
  with the first async workload.
- Auth, real domain models, and business logic — modules are currently stubs.
