# 13 — API Strategy

> The API design for The-Code Adaptive LMS (`maestronexus`). API-first is a core principle ([11_system_architecture.md](11_system_architecture.md)).

## Principles

- **REST + OpenAPI 3.1** as the primary contract; FastAPI generates the spec automatically.
- **Versioned** under `/api/v1`.
- **Resource groups aligned to modules** (one-to-one with bounded contexts).
- **Tenant-scoped**: tenant is derived from the authenticated principal, never trusted from the body.
- **Consistent envelope**: predictable pagination, filtering, errors, and idempotency.
- **Everything important is an API**: integrations, AI, analytics, and admin actions are all callable.

## Authentication and authorization

| Concern | Approach |
|---------|----------|
| User auth | OIDC/SSO for login; JWT access token + refresh token for API sessions |
| Service auth | Service accounts / API keys for integrations and partners |
| Authorization | RBAC + object-level scope on every endpoint ([02_personas_and_permissions.md](02_personas_and_permissions.md)) |
| Tenant binding | `tenant_id` resolved from principal; enforced server-side |

## Resource groups (MVP)

| Group | Base path | Module |
|-------|-----------|--------|
| Auth | `/api/v1/auth` | `iam` |
| Tenants & org | `/api/v1/tenants`, `/departments`, `/programs` | `iam` |
| Users & roles | `/api/v1/users`, `/roles`, `/permissions` | `iam` |
| Courses & versions | `/api/v1/courses`, `/courses/{id}/versions` | `courses` |
| Nodes & dependencies | `/api/v1/courses/{id}/nodes`, `/nodes/{id}/dependencies` | `courses` |
| Classes & enrollments | `/api/v1/classes`, `/enrollments` | `iam`/`courses` |
| Progress & recommendations | `/api/v1/enrollments/{id}/progress`, `/learners/{id}/next-node` | `adaptive` |
| Content & media | `/api/v1/nodes/{id}/content`, `/media` | `content` |
| Assessments & attempts | `/api/v1/assessments`, `/attempts` | `content` |
| Projects & grading | `/api/v1/projects`, `/project-submissions`, `/grades` | `content` |
| Attendance | `/api/v1/classes/{id}/attendance` | `analytics` |
| Reports | `/api/v1/reports/...` | `analytics` |
| AI | `/api/v1/ai/tutor`, `/ai/generate` | `ai` |
| Integrations | `/api/v1/integrations/connectors` | `integrations` |
| Notifications | `/api/v1/notifications` | `notifications` |
| Audit | `/api/v1/audit-logs` | `iam` |

## MVP endpoint checklist (illustrative)

```
# Auth
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
GET    /api/v1/auth/me

# Tenants & org
GET    /api/v1/tenants/{id}
POST   /api/v1/departments
POST   /api/v1/programs

# Users & roles
GET    /api/v1/users
POST   /api/v1/users
GET    /api/v1/users/{id}
POST   /api/v1/users/{id}/roles
GET    /api/v1/roles

# Courses & graph
GET    /api/v1/courses
POST   /api/v1/courses
GET    /api/v1/courses/{id}
POST   /api/v1/courses/{id}/versions
POST   /api/v1/courses/{id}/versions/{v}/publish
GET    /api/v1/courses/{id}/nodes
POST   /api/v1/courses/{id}/nodes
PATCH  /api/v1/nodes/{id}
POST   /api/v1/nodes/{id}/dependencies

# Classes & enrollment
POST   /api/v1/classes
GET    /api/v1/classes/{id}
POST   /api/v1/enrollments
GET    /api/v1/enrollments/{id}

# Progress & adaptive
GET    /api/v1/enrollments/{id}/progress
GET    /api/v1/learners/{id}/next-node
GET    /api/v1/enrollments/{id}/recommendations
POST   /api/v1/enrollments/{id}/events

# Content & assessment
GET    /api/v1/nodes/{id}/content
POST   /api/v1/nodes/{id}/content
POST   /api/v1/media
POST   /api/v1/assessments
POST   /api/v1/attempts

# Projects & grading
POST   /api/v1/projects
POST   /api/v1/project-submissions
GET    /api/v1/classes/{id}/project-submissions
POST   /api/v1/project-submissions/{id}/grade

# Attendance & reports
POST   /api/v1/classes/{id}/attendance/sessions
POST   /api/v1/attendance/sessions/{id}/records
GET    /api/v1/reports/class/{id}
GET    /api/v1/reports/learner/{id}

# AI
POST   /api/v1/ai/tutor/messages
POST   /api/v1/ai/generate
GET    /api/v1/ai/generate/{id}            # review draft
POST   /api/v1/ai/generate/{id}/approve

# Notifications & audit
GET    /api/v1/notifications
GET    /api/v1/audit-logs
```

## Conventions

### Pagination
Cursor-based by default: `?limit=50&cursor=...`; responses include `next_cursor`.

### Filtering & sorting
Explicit query params (`?status=active&sort=-created_at`); no arbitrary query injection.

### Idempotency
Mutating POSTs accept an `Idempotency-Key` header for safe retries (submissions, grading, AI generation).

### Error model
Consistent problem shape:

```json
{
  "error": {
    "code": "out_of_scope",
    "message": "You can only grade submissions in your own classes.",
    "request_id": "..."
  }
}
```

Common codes: `unauthorized` (401), `forbidden` / `out_of_scope` / `wrong_tenant` (403), `not_found` (404), `validation_error` (422), `rate_limited` (429), `conflict` (409).

### Validation
Strict request schemas (Pydantic); reject unknown fields; validate at the boundary.

### Rate limiting
Per-principal and per-tenant limits; stricter limits on AI endpoints (cost control; see [14_security_and_privacy.md](14_security_and_privacy.md)).

## Events and webhooks

Domain events (attempt completed, mastery changed, submission graded, content approved) drive recommendation recompute and notifications, and can be delivered to integrations as webhooks ([10_integrations_and_interoperability.md](10_integrations_and_interoperability.md)).

## Future

| Capability | Status |
|------------|--------|
| GraphQL gateway | Future (if client query flexibility demands it) |
| Event subscriptions (SSE/WebSocket) | Future (live tutor, live dashboards) |
| Public partner API & developer portal | Future |

## Implications for implementation

- Generate and publish the OpenAPI spec from FastAPI; treat it as the contract for the Next.js client and integrations.
- Enforce tenant + RBAC + object scope in a shared dependency applied to every route.
- Keep resource groups aligned with modules so API and architecture stay in sync.

---

Repository: https://github.com/tamers76/maestronexus | Maintainer: The-Code.org / The-Code.ai
