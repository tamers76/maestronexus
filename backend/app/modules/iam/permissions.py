"""Permission catalog and default role mappings (docs/02 RBAC matrix).

Single source of truth for:
  * ``PERMISSIONS`` — every capability key the platform checks.
  * ``ROLES``       — role key -> human label.
  * ``ROLE_PERMISSIONS`` — default permission set granted to each role.

RBAC answers "what kind of action"; object-level scope (ownership/membership,
the 🔒 rows in docs/02) is enforced separately in module services. ``super_admin``
is modeled via ``User.is_superuser`` and bypasses these checks entirely.

Used by the seed script and any module that needs to reason about capabilities.
"""

from __future__ import annotations

# ── Permission keys ──────────────────────────────────────────────────────────
PERMISSIONS: dict[str, str] = {
    "tenant.manage": "Create and manage tenants/institutions",
    "user.manage": "Manage users, roles, and permissions",
    "integration.manage": "Configure integrations and AI settings",
    "course.manage": "Create and edit courses",
    "stage.run": "Run Maestro stage features (intake, content production, ...)",
    "stage.review": "Approve or reject stage runs as an SME (governance)",
    "graph.manage": "Build the learning graph and nodes",
    "mastery.manage": "Define mastery rules and outcomes",
    "content.author": "Author content items",
    "content.ai_generate": "Generate AI content drafts",
    "content.ai_approve": "Approve AI-generated content",
    "class.manage": "Manage classes and cohorts",
    "node.assign": "Assign nodes/lessons to learners",
    "attendance.manage": "Take attendance",
    "project.grade": "Grade projects and review submissions",
    "report.view_class": "View class reports",
    "dashboard.view_institution": "View institution dashboards",
    "node.progress": "Progress through learning nodes",
    "project.submit": "Submit projects",
    "tutor.use": "Use the AI tutor",
    "audit.read": "Read audit logs",
}

# ── Roles ──────────────────────────────────────────────────────────────────
ROLES: dict[str, str] = {
    "super_admin": "Super Admin",
    "institution_admin": "Institution Admin",
    "program_admin": "Program Admin",
    "course_designer": "Course Designer",
    "teacher": "Teacher",
    "teaching_assistant": "Teaching Assistant",
    "learner": "Learner",
    "institution_leader": "Institution Leader",
    "content_creator": "Content Creator",
}

# ── Default role -> permissions ───────────────────────────────────────────────
# super_admin is intentionally omitted (is_superuser bypasses all checks).
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "institution_admin": [
        "user.manage",
        "integration.manage",
        "course.manage",
        "stage.run",
        "stage.review",
        "graph.manage",
        "mastery.manage",
        "content.author",
        "content.ai_generate",
        "content.ai_approve",
        "class.manage",
        "node.assign",
        "attendance.manage",
        "project.grade",
        "report.view_class",
        "dashboard.view_institution",
        "audit.read",
    ],
    "program_admin": [
        "user.manage",
        "integration.manage",
        "course.manage",
        "stage.run",
        "stage.review",
        "graph.manage",
        "mastery.manage",
        "content.author",
        "content.ai_generate",
        "content.ai_approve",
        "class.manage",
        "node.assign",
        "attendance.manage",
        "project.grade",
        "report.view_class",
        "audit.read",
    ],
    "course_designer": [
        "course.manage",
        "stage.run",
        "graph.manage",
        "mastery.manage",
        "content.author",
        "content.ai_generate",
        "content.ai_approve",
    ],
    "teacher": [
        "class.manage",
        "node.assign",
        "attendance.manage",
        "project.grade",
        "report.view_class",
        "tutor.use",
    ],
    "teaching_assistant": [
        "node.assign",
        "attendance.manage",
        "project.grade",
    ],
    "learner": [
        "node.progress",
        "project.submit",
        "tutor.use",
    ],
    "institution_leader": [
        "dashboard.view_institution",
    ],
    "content_creator": [
        "content.author",
        "content.ai_generate",
        "stage.run",
    ],
}
