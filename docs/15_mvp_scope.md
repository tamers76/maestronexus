# 15 — MVP Scope

> The authoritative scope for the first release of The-Code Adaptive LMS (`maestronexus`). When other docs say "MVP," this is the source of truth.

## Goal of the MVP

Prove the core thesis end-to-end: a learner can move through a **node-based course graph** at their own pace, receive a **basic adaptive next-node recommendation**, get help from a **grounded AI tutor**, submit projects, and have teachers grade them — all within a secure, multi-tenant, role-based platform.

## In scope (MVP)

| # | Capability | Reference |
|---|------------|-----------|
| 1 | Authentication (SSO/OIDC + JWT sessions) | [13](13_api_strategy.md), [14](14_security_and_privacy.md) |
| 2 | Role-based access control + object scopes | [02](02_personas_and_permissions.md) |
| 3 | Admin dashboard | [02](02_personas_and_permissions.md), [17](17_ux_principles.md) |
| 4 | Teacher dashboard (class-scoped) | [02](02_personas_and_permissions.md), [17](17_ux_principles.md) |
| 5 | Learner dashboard / Journey View | [03](03_core_user_journeys.md), [17](17_ux_principles.md) |
| 6 | Course creation | [04](04_learning_graph_model.md) |
| 7 | Learning node creation | [04](04_learning_graph_model.md) |
| 8 | Basic node dependency model | [04](04_learning_graph_model.md) |
| 9 | Visual learning-path editor (basic) | [04](04_learning_graph_model.md), [17](17_ux_principles.md) |
| 10 | Content upload (multimodal storage) | [07](07_content_and_assessment_model.md) |
| 11 | Quiz creation | [07](07_content_and_assessment_model.md) |
| 12 | Learner enrollment | [12](12_data_model.md) |
| 13 | Learner progress tracking | [05](05_adaptive_learning_engine.md), [12](12_data_model.md) |
| 14 | Basic adaptive next-node recommendation (rule-based) | [05](05_adaptive_learning_engine.md) |
| 15 | Project submission (per-learner) | [08](08_project_based_learning.md) |
| 16 | Project grading page for teachers (after dashboard) | [08](08_project_based_learning.md) |
| 17 | Attendance | [09](09_attendance_and_reporting.md) |
| 18 | Basic reports | [09](09_attendance_and_reporting.md) |
| 19 | AI tutor grounded in approved course content | [06](06_ai_tutor_and_agents.md) |
| 20 | AI content draft generation for admins/designers | [06](06_ai_tutor_and_agents.md), [07](07_content_and_assessment_model.md) |
| 21 | PostgreSQL database | [11](11_system_architecture.md), [18](18_technical_decisions.md) |
| 22 | API documentation (OpenAPI) | [13](13_api_strategy.md) |
| 23 | Basic audit logs | [14](14_security_and_privacy.md) |

## Out of scope (deferred) and why

| Deferred capability | Why deferred | Target phase |
|---------------------|--------------|--------------|
| Full microservices | Premature; modular monolith is faster and sufficient | When extraction triggers hit ([11](11_system_architecture.md)) |
| Complex AI agents (beyond tutor + content draft) | Focus the AI surface; prove tutor first | Phase 6 |
| Marketplace | Not core to the learning thesis | Future |
| Mobile app | Web-first validation | Future |
| Advanced proctoring | High complexity, niche for MVP | Future ([10](10_integrations_and_interoperability.md)) |
| Full LTI/SCORM engine | Standards work is large; not needed to validate core | Phase 5 ([10](10_integrations_and_interoperability.md)) |
| Complex predictive analytics | Needs data + models; descriptive analytics first | Phase 4 ([09](09_attendance_and_reporting.md)) |
| AI-driven best-modality recommendation | Requires signals/models; manual alternatives first | Phase 6 ([07](07_content_and_assessment_model.md)) |

The architecture explicitly allows all deferred items later without rework ([11](11_system_architecture.md), [18](18_technical_decisions.md)).

## Acceptance criteria by epic

| Epic | Done when |
|------|-----------|
| Auth & RBAC | A user logs in via SSO, receives a scoped session, and is blocked from out-of-tenant/out-of-scope actions (verified by tests). |
| Course graph | A designer creates a course, adds nodes, draws `requires`/`mastery_gate` dependencies, and publishes a version. |
| Enrollment & progress | A learner enrolls (pinned to a version) and node states transition correctly (locked → available → completed → mastered). |
| Adaptive recommendation | `GET /learners/{id}/next-node` returns a node with a human-readable reason; teacher assignment overrides the engine. |
| Content & quizzes | Content uploads and quizzes attach to nodes; only approved content is served. |
| AI tutor | The tutor answers grounded in approved content, refuses to answer graded items, and can escalate to a teacher. |
| AI content draft | A designer generates a draft that lands in review and only becomes a content item after approval. |
| Projects | A learner submits per-learner; a teacher grades only own-class submissions via the grading page after the dashboard. |
| Attendance & reports | A teacher marks attendance for own classes and views basic class reports; admins see scoped reports. |
| Platform | OpenAPI is published; audit logs capture privileged actions; tenant isolation holds. |

## MVP vs Future (single reference table)

| Capability area | MVP | Future |
|-----------------|:---:|:------:|
| Node graph + basic dependencies | ✅ | ✅ |
| Rule-based adaptive engine | ✅ | ✅ |
| AI-enhanced adaptive engine | ➖ | ✅ |
| Grounded AI tutor | ✅ | ✅ |
| Multi-agent orchestration | ➖ | ✅ |
| AI content draft + human review | ✅ | ✅ |
| AI media generation (video/TTS/STT) | ➖ | ✅ |
| Multimodal storage | ✅ | ✅ |
| AI best-modality recommendation | ➖ | ✅ |
| Projects + per-learner grading | ✅ | ✅ |
| Attendance + basic reports | ✅ | ✅ |
| Predictive analytics | ➖ | ✅ |
| Outcome/skills mapping | Basic | Rich/visual |
| Standards (LTI/SCORM/xAPI/QTI) | ➖ | ✅ |
| BI export / LRS | ➖ | ✅ |
| Payments / marketplace / mobile | ➖ | ✅ |

## Implications for implementation

- Build to the acceptance criteria above; resist scope creep into deferred items.
- Keep abstractions (AI, storage, integrations) in place so Future items slot in without rework.
- Sequence the build per [16_roadmap.md](16_roadmap.md).

---

Repository: https://github.com/tamers76/maestronexus | Maintainer: The-Code.org / The-Code.ai
