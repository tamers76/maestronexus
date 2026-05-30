# 19 — Open Questions

> Consolidated decisions to resolve for The-Code Adaptive LMS (`maestronexus`). Each has a suggested owner and the phase by which it should be settled.

## How to use this document

These are deliberately unresolved. Resolve them as the project matures; when a question is settled, record the decision in the relevant doc (and, for technology, in [18_technical_decisions.md](18_technical_decisions.md)).

## Product

| ID | Question | Owner | Resolve by |
|----|----------|-------|------------|
| P1 | Final product brand name (replacing "The-Code Adaptive LMS") | Product/Founders | Before public launch |
| P2 | Primary target market first (K-12, higher-ed, corporate, government) | Product | Phase 0–1 |
| P3 | Self-serve vs institution-sold go-to-market | Product/Founders | Phase 4 |
| P4 | Parent/Guardian persona inclusion timing | Product | Phase 4–5 |

## Pedagogy

| ID | Question | Owner | Resolve by |
|----|----------|-------|------------|
| PE1 | Default mastery threshold and whether it varies by node type | Learning Science | Phase 2 |
| PE2 | How confidence is captured (self-report vs inferred) and weighted | Learning Science | Phase 2 |
| PE3 | Remediation philosophy: re-teach same content vs alternative modality first | Learning Science | Phase 2–3 |
| PE4 | How skills frameworks/standards are sourced and maintained per tenant | Learning Science/Product | Phase 4 |

## Technical

| ID | Question | Owner | Resolve by |
|----|----------|-------|------------|
| T1 | Celery vs ARQ for background jobs (footprint vs features) | Engineering | Phase 1 |
| T2 | When to introduce an external vector DB beyond `pgvector` | Engineering | Phase 3 |
| T3 | When to introduce OpenSearch/Elasticsearch beyond Postgres FTS | Engineering | Phase 4–5 |
| T4 | First module to extract from the monolith (likely AI workers) | Engineering | When triggers fire ([11](11_system_architecture.md)) |
| T5 | Multi-tenancy: when (if ever) to move specific tenants to schema/DB isolation | Engineering | Phase 4+ |
| T6 | Real-time transport for live tutor/dashboards (SSE vs WebSocket) | Engineering | Phase 3 |

## AI

| ID | Question | Owner | Resolve by |
|----|----------|-------|------------|
| AI1 | Default LLM provider and model per capability (tutor vs generation) | Engineering/Product | Phase 3 |
| AI2 | Per-tenant AI cost/budget model and limits | Product/Engineering | Phase 3 |
| AI3 | Acceptable grounding/citation threshold before fallback | Learning Science/Engineering | Phase 3 |
| AI4 | Policy for AI-assisted grading feedback (advisory only?) | Product/Learning Science | Phase 3–4 |

## Integrations

| ID | Question | Owner | Resolve by |
|----|----------|-------|------------|
| I1 | UAE Pass / national identity feasibility and priority | Product/Engineering | Phase 5 |
| I2 | Standards priority order (LTI 1.3 vs SCORM vs xAPI first) | Product | Phase 5 |
| I3 | Whether to act as an LRS or integrate with an external LRS | Engineering | Phase 4–5 |
| I4 | Which communication channels are first-class beyond email | Product | Phase 5 |

## Legal & compliance

| ID | Question | Owner | Resolve by |
|----|----------|-------|------------|
| L1 | Repository license for `maestronexus` (proprietary vs source-available vs OSS) | Founders/Legal | Phase 0–1 |
| L2 | Applicable regimes (FERPA, GDPR, regional) per target market | Legal | Phase 1 |
| L3 | Data residency requirements per tenant/region | Legal/Engineering | Phase 4–5 |
| L4 | Minors' data consent and guardian flows | Legal/Product | Before K-12 launch |
| L5 | AI usage disclosure and data-processing terms | Legal | Phase 3 |

## Branding

| ID | Question | Owner | Resolve by |
|----|----------|-------|------------|
| B1 | Relationship between repo codename `maestronexus` and final product brand | Product/Founders | Before launch |
| B2 | Domain and visual identity (The-Code.org / The-Code.ai) | Product/Founders | Before launch |

## Implications for implementation

- None of these block Phase 1; they are tracked so decisions are explicit and recorded when made.
- Technology resolutions should update [18_technical_decisions.md](18_technical_decisions.md); scope resolutions should update [15_mvp_scope.md](15_mvp_scope.md).

---

Repository: https://github.com/tamers76/maestronexus | Maintainer: The-Code.org / The-Code.ai
