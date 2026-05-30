# 12 — Data Model

> Core entities and relationships for The-Code Adaptive LMS (`maestronexus`). This is a conceptual model, not a final migration.

## Conventions

- **Every tenant-owned table carries `tenant_id`** (multi-tenant isolation; see [14_security_and_privacy.md](14_security_and_privacy.md)).
- **UUID primary keys** (`id`) for all entities.
- **Soft deletes** via `deleted_at` for recoverable records (enrollments, content, submissions).
- **Auditing fields** `created_at`, `updated_at`, `created_by` on mutable entities.
- **Versioning**: courses and content use explicit version entities rather than in-place mutation of published artifacts.
- **Embeddings**: `pgvector` columns live on content/index tables, not on hot transactional tables.

## Entity groups

The model is organized into five subgraphs: Organization & Identity, Course Graph, Enrollment & Progress, Content & Assessment, and Skills & Outcomes. Cross-cutting entities (Notification, AI Interaction, AI Generated Content, Integration Connector, Audit Log) attach across groups.

### Organization & Identity

```mermaid
erDiagram
  TENANT ||--o{ CAMPUS : has
  TENANT ||--o{ DEPARTMENT : has
  DEPARTMENT ||--o{ PROGRAM : offers
  TENANT ||--o{ USER : has
  USER ||--o{ USER_ROLE : assigned
  ROLE ||--o{ USER_ROLE : grants
  ROLE ||--o{ ROLE_PERMISSION : includes
  PERMISSION ||--o{ ROLE_PERMISSION : in
  USER ||--o{ LEARNER_PROFILE : has
  USER ||--o{ TEACHER_ASSIGNMENT : has

  TENANT {
    uuid id
    string name
    string slug
    jsonb settings
  }
  USER {
    uuid id
    uuid tenant_id
    string email
    string display_name
    string status
  }
  ROLE {
    uuid id
    uuid tenant_id
    string key
    string name
  }
  PERMISSION {
    uuid id
    string key
    string description
  }
  LEARNER_PROFILE {
    uuid id
    uuid user_id
    jsonb preferences
    jsonb goals
  }
  TEACHER_ASSIGNMENT {
    uuid id
    uuid user_id
    uuid class_id
    string role_in_class
  }
```

### Course Graph

```mermaid
erDiagram
  PROGRAM ||--o{ COURSE : contains
  COURSE ||--o{ COURSE_VERSION : versioned_as
  COURSE_VERSION ||--o{ LEARNING_NODE : contains
  LEARNING_NODE ||--o{ NODE_DEPENDENCY : source
  LEARNING_NODE ||--o{ NODE_DEPENDENCY : target
  COURSE_VERSION ||--o{ LEARNING_PATH : defines

  COURSE {
    uuid id
    uuid tenant_id
    uuid program_id
    string title
    string status
  }
  COURSE_VERSION {
    uuid id
    uuid course_id
    int version
    string state
    timestamp published_at
  }
  LEARNING_NODE {
    uuid id
    uuid course_version_id
    string type
    string title
    jsonb learning_objective
    jsonb mastery_rule
    jsonb completion_rule
    int estimated_duration
    jsonb metadata
  }
  NODE_DEPENDENCY {
    uuid id
    uuid source_node_id
    uuid target_node_id
    string dependency_type
  }
  LEARNING_PATH {
    uuid id
    uuid course_version_id
    string kind
    jsonb config
  }
```

### Enrollment & Progress

```mermaid
erDiagram
  CLASS ||--o{ ENROLLMENT : has
  COURSE_VERSION ||--o{ ENROLLMENT : pinned_to
  USER ||--o{ ENROLLMENT : enrolls
  ENROLLMENT ||--o{ NODE_PROGRESS : tracks
  LEARNING_NODE ||--o{ NODE_PROGRESS : for
  ENROLLMENT ||--o{ MASTERY_RECORD : accrues
  ENROLLMENT ||--o{ RECOMMENDATION : receives

  CLASS {
    uuid id
    uuid tenant_id
    uuid course_id
    uuid teacher_id
    string name
  }
  ENROLLMENT {
    uuid id
    uuid tenant_id
    uuid user_id
    uuid class_id
    uuid course_version_id
    string status
  }
  NODE_PROGRESS {
    uuid id
    uuid enrollment_id
    uuid node_id
    string state
    int attempts
    int time_spent_seconds
    float confidence
    timestamp completed_at
  }
  MASTERY_RECORD {
    uuid id
    uuid enrollment_id
    uuid node_id
    uuid skill_id
    float score
    string status
    jsonb evidence
  }
  RECOMMENDATION {
    uuid id
    uuid enrollment_id
    uuid recommended_node_id
    string reason
    string source
    timestamp created_at
  }
```

### Content & Assessment

```mermaid
erDiagram
  LEARNING_NODE ||--o{ CONTENT_ITEM : presents
  CONTENT_ITEM ||--o{ MEDIA_ASSET : references
  LEARNING_NODE ||--o{ ASSESSMENT : includes
  ASSESSMENT ||--o{ QUESTION : contains
  ASSESSMENT ||--o{ ATTEMPT : measured_by
  ATTEMPT ||--o{ SUBMISSION : produces
  PROJECT ||--o{ PROJECT_SUBMISSION : receives
  PROJECT ||--o{ RUBRIC : graded_by
  PROJECT_SUBMISSION ||--o{ GRADE : scored_by
  GRADE ||--o{ FEEDBACK : carries

  CONTENT_ITEM {
    uuid id
    uuid node_id
    string modality
    int version
    jsonb body
    string approval_status
  }
  MEDIA_ASSET {
    uuid id
    uuid tenant_id
    string storage_key
    string mime_type
    int size_bytes
  }
  ASSESSMENT {
    uuid id
    uuid node_id
    string type
    jsonb config
  }
  QUESTION {
    uuid id
    uuid assessment_id
    string type
    jsonb prompt
    jsonb answer_key
  }
  ATTEMPT {
    uuid id
    uuid enrollment_id
    uuid assessment_id
    float score
    timestamp submitted_at
  }
  PROJECT {
    uuid id
    uuid node_id
    bool collaborative
    int max_submissions
  }
  PROJECT_SUBMISSION {
    uuid id
    uuid project_id
    uuid learner_id
    int attempt_no
    string status
  }
  RUBRIC {
    uuid id
    uuid project_id
    jsonb criteria
  }
  GRADE {
    uuid id
    uuid submission_id
    uuid grader_id
    float score
    jsonb rubric_scores
  }
  FEEDBACK {
    uuid id
    uuid grade_id
    string author_type
    text body
  }
```

### Skills & Outcomes

```mermaid
erDiagram
  SKILL ||--o{ NODE_SKILL : tagged_on
  LEARNING_NODE ||--o{ NODE_SKILL : develops
  COMPETENCY ||--o{ SKILL : groups
  LEARNING_OUTCOME ||--o{ OUTCOME_MAPPING : mapped
  LEARNING_NODE ||--o{ OUTCOME_MAPPING : covers
  ASSESSMENT ||--o{ OUTCOME_MAPPING : evidences

  SKILL {
    uuid id
    uuid tenant_id
    string name
    string framework
  }
  COMPETENCY {
    uuid id
    uuid tenant_id
    string name
  }
  LEARNING_OUTCOME {
    uuid id
    uuid tenant_id
    string kind
    string code
    text statement
  }
  OUTCOME_MAPPING {
    uuid id
    uuid outcome_id
    uuid node_id
    uuid assessment_id
    string coverage_level
  }
```

### Attendance

```mermaid
erDiagram
  CLASS ||--o{ ATTENDANCE_SESSION : schedules
  ATTENDANCE_SESSION ||--o{ ATTENDANCE_RECORD : has
  USER ||--o{ ATTENDANCE_RECORD : marked_for

  ATTENDANCE_SESSION {
    uuid id
    uuid tenant_id
    uuid class_id
    timestamp scheduled_at
    string mode
  }
  ATTENDANCE_RECORD {
    uuid id
    uuid session_id
    uuid learner_id
    string status
    timestamp marked_at
    uuid marked_by
  }
```

### Cross-cutting entities

```mermaid
erDiagram
  USER ||--o{ NOTIFICATION : receives
  USER ||--o{ AI_INTERACTION : initiates
  AI_INTERACTION ||--o{ AI_GENERATED_CONTENT : may_produce
  TENANT ||--o{ INTEGRATION_CONNECTOR : configures
  TENANT ||--o{ AUDIT_LOG : records

  NOTIFICATION {
    uuid id
    uuid tenant_id
    uuid user_id
    string channel
    string type
    string status
  }
  AI_INTERACTION {
    uuid id
    uuid tenant_id
    uuid user_id
    string agent
    jsonb context_refs
    timestamp created_at
  }
  AI_GENERATED_CONTENT {
    uuid id
    uuid interaction_id
    string target_type
    jsonb draft
    string review_status
  }
  INTEGRATION_CONNECTOR {
    uuid id
    uuid tenant_id
    string category
    string provider
    jsonb config
    string status
  }
  AUDIT_LOG {
    uuid id
    uuid tenant_id
    uuid actor_id
    string action
    string object_type
    uuid object_id
    jsonb metadata
    timestamp created_at
  }
```

## Entity reference

| Entity | Group | Notes |
|--------|-------|-------|
| Tenant / Institution | Org | Isolation boundary |
| Campus | Org | Optional physical/logical site |
| Department | Org | Groups programs |
| Program | Org | Groups courses; PLOs attach here |
| Course | Course Graph | Editable container |
| Course Version | Course Graph | Immutable published snapshot |
| Learning Node | Course Graph | Atomic learning unit |
| Node Dependency | Course Graph | Directed edge with type |
| Learning Path | Course Graph | Named path configuration |
| Class / Cohort | Enrollment | Teacher-owned group |
| Enrollment | Enrollment | Learner ↔ class ↔ version |
| User | Identity | Any actor |
| Role / Permission | Identity | RBAC (see [02](02_personas_and_permissions.md)) |
| Teacher Assignment | Identity | Teacher ↔ class scope |
| Learner Profile | Identity | Preferences, goals |
| Content Item | Content | Modality-specific body, versioned |
| Media Asset | Content | Object-storage reference |
| Assessment / Question | Assessment | Question bank + config |
| Attempt / Submission | Assessment | Learner responses |
| Project / Project Submission | Projects | Per-learner submissions |
| Rubric / Grade / Feedback | Projects | Grading artifacts |
| Attendance Session / Record | Attendance | Class-scoped |
| Skill / Competency | Skills | Trackable capabilities |
| Learning Outcome | Outcomes | CLO/PLO |
| Outcome Mapping | Outcomes | Coverage matrix |
| Mastery Record | Progress | Mastery evidence |
| Recommendation | Progress | Adaptive engine output |
| AI Interaction | Cross-cutting | Tutor/agent calls |
| AI Generated Content | Cross-cutting | Drafts pending review |
| Notification | Cross-cutting | Multi-channel |
| Integration Connector | Cross-cutting | Provider config |
| Audit Log | Cross-cutting | Privileged action trail |

## Indexing and performance notes

- Composite index on `(tenant_id, ...)` for every tenant-scoped query path.
- `NODE_PROGRESS` indexed by `(enrollment_id, node_id)` and `(enrollment_id, state)` for journey rendering.
- `NODE_DEPENDENCY` indexed by both `source_node_id` and `target_node_id` for forward/backward traversal.
- Vector indexes (`pgvector` HNSW/IVF) only on content/index tables used by RAG (see [06_ai_tutor_and_agents.md](06_ai_tutor_and_agents.md)).
- `AUDIT_LOG` is append-only and partitioned by time.

## Implications for implementation

- Keep the course graph (definition) separate from per-learner progress (state). The graph is shared/immutable per version; progress is per enrollment.
- Mastery records are the source of truth for `mastery_gate` evaluation in [04_learning_graph_model.md](04_learning_graph_model.md).
- AI-generated content is never directly published — it lands in `AI_GENERATED_CONTENT` with `review_status` and flows into `CONTENT_ITEM` only after approval (see [07_content_and_assessment_model.md](07_content_and_assessment_model.md)).

---

Repository: https://github.com/tamers76/maestronexus | Maintainer: The-Code.org / The-Code.ai
