# The-Code Adaptive LMS (codename: `maestronexus`)

> An AI-native, learner-centric, adaptive Learning Management System built by **The-Code.org / The-Code.ai**.

- **Repository:** https://github.com/tamers76/maestronexus
- **Clone:** `git clone https://github.com/tamers76/maestronexus.git`
- **Product name (placeholder):** The-Code Adaptive LMS / Project Adaptive LMS (branding not yet finalized)
- **Engineering codename:** `maestronexus` (Maestro Nexus)
- **Status:** Documentation foundation phase. No application code yet.

---

## What this is

Traditional LMS platforms (Moodle, Blackboard, Canvas) are mostly content repositories that assume every learner walks the same linear path. The-Code Adaptive LMS rethinks learning as an **adaptive journey across a graph of learning nodes**, where each learner moves at their own pace and an adaptive engine decides what they need next to reach mastery.

The platform is:

- **Learner-centric** — the unit of progress is the learner, not the course.
- **AI-native** — an AI tutor, content generation, and (later) multi-agent orchestration are first-class.
- **Adaptive** — a node graph with prerequisites, mastery gates, remediation, and enrichment paths.
- **API-first, modular, and interoperable** — clean boundaries, provider abstractions, standards-ready.

> Core philosophy: **Learning should not be a linear course. Learning should be an adaptive journey.** The system never just asks "what lesson comes next?" — it asks "what does this learner need next to reach mastery?"

---

## Current phase: documentation only

This repository currently contains **planning and design documentation**. There is intentionally no frontend, backend, infrastructure, or dependency code yet. The goal is a foundation strong enough that a future engineering team (human or AI agent) can begin building with confidence and a shared understanding of scope, architecture, and trade-offs.

---

## How to read the docs

Read in numeric order for the full narrative. For a build-oriented reading, follow `00` then jump to `15` (MVP scope) and `16` (roadmap).

| # | Document | What it covers |
|---|----------|----------------|
| 00 | [docs/00_project_overview.md](docs/00_project_overview.md) | Executive summary, glossary, differentiators, doc map |
| 01 | [docs/01_product_vision.md](docs/01_product_vision.md) | Vision, philosophy, competitive positioning, non-goals |
| 02 | [docs/02_personas_and_permissions.md](docs/02_personas_and_permissions.md) | Personas, RBAC matrix, object-level scopes |
| 03 | [docs/03_core_user_journeys.md](docs/03_core_user_journeys.md) | End-to-end journeys with diagrams |
| 04 | [docs/04_learning_graph_model.md](docs/04_learning_graph_model.md) | Node taxonomy, dependencies, path types |
| 05 | [docs/05_adaptive_learning_engine.md](docs/05_adaptive_learning_engine.md) | Rule-based MVP engine and AI-enhanced future |
| 06 | [docs/06_ai_tutor_and_agents.md](docs/06_ai_tutor_and_agents.md) | AI tutor principles, guardrails, agent catalog |
| 07 | [docs/07_content_and_assessment_model.md](docs/07_content_and_assessment_model.md) | Content, assessment, mastery rules, AI content workflow |
| 08 | [docs/08_project_based_learning.md](docs/08_project_based_learning.md) | Project submissions, rubrics, teacher grading |
| 09 | [docs/09_attendance_and_reporting.md](docs/09_attendance_and_reporting.md) | Attendance, reports, analytics |
| 10 | [docs/10_integrations_and_interoperability.md](docs/10_integrations_and_interoperability.md) | Integration categories and standards |
| 11 | [docs/11_system_architecture.md](docs/11_system_architecture.md) | Logical/deployment architecture, multi-tenancy |
| 12 | [docs/12_data_model.md](docs/12_data_model.md) | Entities and ER diagrams |
| 13 | [docs/13_api_strategy.md](docs/13_api_strategy.md) | API design, versioning, endpoint catalog |
| 14 | [docs/14_security_and_privacy.md](docs/14_security_and_privacy.md) | Security controls, privacy, AI safety |
| 15 | [docs/15_mvp_scope.md](docs/15_mvp_scope.md) | MVP in/out of scope, acceptance criteria |
| 16 | [docs/16_roadmap.md](docs/16_roadmap.md) | Phases 0–6 with timeline and risks |
| 17 | [docs/17_ux_principles.md](docs/17_ux_principles.md) | UX tenets and information architecture |
| 18 | [docs/18_technical_decisions.md](docs/18_technical_decisions.md) | ADR-style decisions, dev stack, repo layout |
| 19 | [docs/19_open_questions.md](docs/19_open_questions.md) | Consolidated open questions |

---

## Recommended stack (summary)

Full rationale and trade-offs live in [docs/18_technical_decisions.md](docs/18_technical_decisions.md).

| Layer | Recommendation |
|-------|----------------|
| Frontend | Next.js (App Router) + TypeScript + Tailwind + shadcn/ui |
| Learning graph UI | React Flow (`@xyflow/react`) |
| Backend | Python + FastAPI (modular monolith for MVP) |
| Database | PostgreSQL + `pgvector` |
| Cache / queue | Redis + Celery (or ARQ) |
| Storage | Azure Blob (prod) / MinIO (dev) |
| Deploy | Docker Compose (dev) → Azure Container Apps (first prod) |

---

## Contributing

All issues, discussions, and pull requests live on the canonical repository: **https://github.com/tamers76/maestronexus**. There is no alternate repository. Branch from `main`; `main` is protected.

---

## Project references

- Repository: https://github.com/tamers76/maestronexus
- Maintainer: The-Code.org / The-Code.ai
