# AGENTS.md

## Cursor Cloud specific instructions

### Product overview

**The-Code Adaptive LMS** (`maestronexus`) is a two-app repo: FastAPI backend (`backend/`) and Next.js frontend (`frontend/`). Authoritative local run details are in [DEVELOPMENT.md](DEVELOPMENT.md) (written for Windows-native services); on Linux/cloud VMs use the notes below.

### Services (current scaffold)

| Service | Port | Notes |
|---------|------|--------|
| PostgreSQL | 5432 | DB `maestronexus`, user `maestro` / `maestro-dev-secret123` |
| Redis | 6379 | No password in local dev |
| MinIO API | 9000 | Root user `maestro` / `maestro-dev-secret123`; bucket `maestronexus` |
| Backend (uvicorn) | 8000 | Readiness: `GET /health/ready` |
| Frontend (Next.js) | 3000 | Home page polls backend readiness |

There is **no** `docker-compose` in the repo yet. Infra must be started natively (or add Compose yourself).

### Linux / cloud VM: first-time infra

These steps are **not** in the VM update script (one-time or host-level):

1. **PostgreSQL**: create role/db if missing (`CREATE USER maestro ...`, `CREATE DATABASE maestronexus OWNER maestro`). Start with `sudo pg_ctlcluster 16 main start` if the service did not auto-start.
2. **Redis**: `redis-server --daemonize yes` (or `sudo service redis-server start`).
3. **MinIO**: run `minio server <data-dir> --address ":9000" --console-address ":9001"` with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` set to the dev credentials in `DEVELOPMENT.md`. Create bucket: `mc alias set local http://localhost:9000 maestro maestro-dev-secret123 && mc mb local/maestronexus --ignore-existing`.
4. **Backend env**: `cp backend/.env.example backend/.env` (file is gitignored).
5. **Migrations**: `cd backend && uv run alembic upgrade head`.

### Running dev servers

Use **tmux** for long-lived processes (MinIO, backend, frontend). Example:

```bash
# Backend
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

Open http://localhost:3000 — the home page should show PostgreSQL, Redis, and MinIO/S3 as **healthy**.

### Lint / test / build

| App | Lint | Tests | Dev run | Build |
|-----|------|-------|---------|-------|
| Backend | `cd backend && uv run ruff check .` | `uv run pytest` (no tests in repo yet) | uvicorn above | N/A for setup |
| Frontend | `cd frontend && npm run lint` | none configured | `npm run dev` | `npm run build` |

### Gotchas

- **Missing module**: If uvicorn fails with `No module named 'app.modules.ai.providers'`, ensure `backend/app/modules/ai/providers.py` exists (scaffold registry for the AI module).
- **Readiness 503 on storage**: MinIO bucket `maestronexus` must exist before `/health/ready` passes.
- **DEVELOPMENT.md** references Windows services and gitignored `.localdev/start-minio.ps1`; on Linux, start equivalent processes manually as above.
- **Node**: Use Node 22.x; repo has no `.nvmrc` but `DEVELOPMENT.md` documents 22.x.
- **Python**: Backend pins 3.12 via `backend/.python-version`; use `uv sync --extra dev`.
