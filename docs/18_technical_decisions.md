# 18 — Technical Decisions

> ADR-style record of key technology choices for The-Code Adaptive LMS (`maestronexus`), with alternatives and revisit triggers.

## Repository and delivery

| Item | Value |
|------|-------|
| Canonical repository | https://github.com/tamers76/maestronexus |
| Remote `origin` | `https://github.com/tamers76/maestronexus.git` |
| Default branch | `main` (protected) |
| Branch strategy | Short-lived feature branches → PR → `main` |
| CI/CD | GitHub Actions (Future — not yet configured) |
| Issue/PR tracking | GitHub Issues/PRs on `maestronexus` only |

## Decision summary

| # | Decision | Choice | Status |
|---|----------|--------|--------|
| D1 | Backend framework | Python + FastAPI | Accepted |
| D2 | Frontend framework | Next.js (App Router) + TypeScript | Accepted |
| D3 | Styling/components | Tailwind CSS + shadcn/ui | Accepted |
| D4 | Learning graph UI | React Flow (`@xyflow/react`) | Accepted |
| D5 | Primary database | PostgreSQL 16 | Accepted |
| D6 | Vector storage | `pgvector` in Postgres (MVP) | Accepted |
| D7 | Cache & queue | Redis + Celery (or ARQ) | Accepted |
| D8 | Object storage | Azure Blob (prod) / MinIO (dev) | Accepted |
| D9 | Architecture style | Modular monolith first | Accepted |
| D10 | Search | Postgres FTS first | Accepted |
| D11 | Deployment | Docker Compose (dev) → Azure Container Apps (prod) | Accepted |
| D12 | AI access | Provider abstraction layer | Accepted |

## D1 — Backend: Python + FastAPI

**Decision:** Use Python 3.12 with FastAPI as the primary backend.

**Why:** The team is strong in Python; FastAPI offers first-class OpenAPI generation, async I/O, Pydantic validation, and an excellent fit for AI/RAG workflows. It keeps clean module boundaries within one deployable.

**Alternative considered:** Node.js/NestJS — strong for real-time and a unified TS stack, but a weaker fit given team strengths and the heavy AI orchestration in early phases.

**Revisit if:** real-time features dominate, or the org standardizes on a single TS stack end-to-end.

## D2–D4 — Frontend

**Decision:** Next.js (App Router) + TypeScript, Tailwind CSS, shadcn/ui, and React Flow for the learning-graph editor ([04_learning_graph_model.md](04_learning_graph_model.md)).

**Why:** SSR/SSG suits dashboards and content; the ecosystem is mature; React Flow is a proven node-edge editor for the signature graph experience ([17_ux_principles.md](17_ux_principles.md)).

**Revisit if:** the graph editor outgrows React Flow's capabilities or a different rendering approach is needed for very large graphs.

## D5–D6 — Database and vectors

**Decision:** PostgreSQL as the core relational store; `pgvector` for embeddings in the MVP.

**Why:** A single store reduces operational complexity. `pgvector` is sufficient for MVP-scale RAG ([06_ai_tutor_and_agents.md](06_ai_tutor_and_agents.md)).

**Alternative considered:** dedicated vector DB (e.g. external service) — unnecessary complexity at MVP scale.

**Revisit if:** embedding volume or latency requirements exceed what `pgvector` serves comfortably; then add an external vector DB behind the AI module's interface.

## D7 — Cache and background jobs

**Decision:** Redis for caching and as the broker for background jobs via Celery (or ARQ for a lighter footprint).

**Why:** AI generation, indexing, media processing, notifications, imports, and analytics all need async processing ([11_system_architecture.md](11_system_architecture.md)).

**Revisit if:** workflow orchestration grows complex enough to warrant a dedicated workflow engine.

## D8 — Object storage

**Decision:** Azure Blob Storage in production, MinIO locally, behind a storage-provider abstraction.

**Why:** Aligns with the Azure deployment direction; the abstraction keeps AWS S3/GCS viable ([10_integrations_and_interoperability.md](10_integrations_and_interoperability.md)).

## D9 — Modular monolith first

**Decision:** Build one deployable FastAPI app with strict module boundaries; defer microservices.

**Why:** Faster MVP, lower operational burden, clean boundaries now, clear extraction path later. Extraction triggers and likely first splits (AI workers, notifications, analytics) are documented in [11_system_architecture.md](11_system_architecture.md).

**Trade-off:** Requires discipline (no cross-module DB access). Accepted in exchange for speed and simplicity.

**Revisit if:** independent scaling, team ownership, or compliance isolation forces extraction.

## D10 — Search

**Decision:** PostgreSQL full-text search first.

**Why:** Avoids running OpenSearch/Elasticsearch at MVP.

**Revisit if:** search relevance/scale needs exceed Postgres FTS → introduce OpenSearch/Elasticsearch.

## D11 — Deployment

**Decision:** Docker Compose for local dev; Azure Container Apps for first production; AKS later if warranted.

**Why:** Container Apps is simpler than AKS for an early modular monolith; AKS is justified once multi-service scaling/ownership emerges.

## Local development stack (Docker Compose services)

| Service | Purpose |
|---------|---------|
| `api` | FastAPI core API |
| `worker` | Background job worker |
| `db` | PostgreSQL + `pgvector` |
| `redis` | Cache and job broker |
| `minio` | Local S3-compatible object storage |
| `web` | Next.js frontend |

(These describe intended services; no code or compose file is created in this documentation phase.)

## Repository layout preview (intent only)

```
maestronexus/
  docs/                # this documentation set
  backend/             # FastAPI modular monolith (future)
    iam/ courses/ adaptive/ content/ ai/ analytics/ notifications/ integrations/
  frontend/            # Next.js app (future)
  infra/               # Docker Compose, deployment config (future)
  README.md
```

This is a planned monorepo layout for `maestronexus`; directories are created when implementation begins, not now.

## Implications for implementation

- Start the backend as one FastAPI app with the module packages above; enforce boundaries via service interfaces.
- Put all third-party providers (AI, storage, comms, identity) behind abstractions from the first commit.
- Keep `pgvector`, Postgres FTS, and Container Apps as the simple defaults; the abstractions make later upgrades non-breaking.

---

Repository: https://github.com/tamers76/maestronexus | Maintainer: The-Code.org / The-Code.ai
