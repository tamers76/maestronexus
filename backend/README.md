# maestronexus — Backend

FastAPI modular monolith for The-Code Adaptive LMS. See [../docs/11_system_architecture.md](../docs/11_system_architecture.md) and [../docs/18_technical_decisions.md](../docs/18_technical_decisions.md).

## Requirements

- Python 3.12 (managed by [uv](https://docs.astral.sh/uv/))
- Local services running: PostgreSQL (`:5432`), Redis/Memurai (`:6379`), MinIO (`:9000`)

## Setup

```bash
cd backend
uv sync --extra dev          # create .venv and install deps
copy .env.example .env        # Windows (already provided in this repo)
```

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

- API docs (Swagger): http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json
- Liveness: http://localhost:8000/health
- Readiness (checks Postgres + Redis + MinIO): http://localhost:8000/health/ready

## Layout

```
backend/
  app/
    main.py            # FastAPI app + lifespan + middleware
    core/              # config, database, redis, storage, errors
    api/               # health probes + /api/v1 router aggregator
    modules/           # bounded contexts (iam, courses, adaptive, content,
                       #   ai, analytics, notifications, integrations)
  migrations/          # Alembic (async) — versions added as models land
  pyproject.toml
```

## Migrations (Alembic)

Models are added per module under `app/modules/<module>/models.py` and imported in
`migrations/env.py`. Then:

```bash
uv run alembic revision --autogenerate -m "create <thing>"
uv run alembic upgrade head
```

## Conventions

- API is versioned under `/api/v1`; resource groups map 1:1 to modules.
- Errors use the envelope `{ "error": { "code", "message", "request_id" } }`.
- Cross-module access goes through service interfaces — never import another
  module's models directly.
