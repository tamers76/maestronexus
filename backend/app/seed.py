"""Idempotent dev seed: tenant, permission catalog, roles, and demo users.

Run from the backend dir:

    uv run python -m app.seed

Creates (if missing):
  * tenant ``the-code`` (slug)
  * every permission in ``app.modules.iam.permissions.PERMISSIONS``
  * every role in ``ROLES`` with its default permission grants
  * demo users (login = username, password ``pass``):
      - super       (super_admin / is_superuser)
      - admin       (institution_admin)
      - designer    (course_designer)
      - teacher     (teacher)
      - learner     (learner)
  * one fully Blueprint-ready demo course (``MAESTRO-101``) — refined CLOs, a
    published learning-node graph, an approved contribution-assessment blueprint,
    subtopics, approved design artifacts, a class, and a learner enrollment with
    node progress — so Studio, the learner journey, and faculty dashboards all
    render with real data end to end.

Safe to run repeatedly. Also removes the older ``*@the-code.dev`` demo users.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.core.database import SessionLocal, engine
from app.core.security import hash_password

# Import every module's models so the mapper registry is complete before flush
# (cross-module string FKs, e.g. blueprint -> stage_runs, courses -> programs).
from app.modules.adaptive import models as _adaptive_models  # noqa: F401
from app.modules.ai import models as _ai_models  # noqa: F401
from app.modules.attendance import models as _attendance_models  # noqa: F401
from app.modules.blueprint import models as _blueprint_models  # noqa: F401
from app.modules.blueprint.models import (
    ContributionAssessment,
    CourseDesignArtifact,
    CourseSubtopic,
)
from app.modules.content import models as _content_models  # noqa: F401
from app.modules.courses import models as _courses_models  # noqa: F401
from app.modules.courses.models import (
    Course,
    CourseVersion,
    LearningNode,
    LearningOutcome,
    NodeDependency,
)
from app.modules.enrollment import models as _enrollment_models  # noqa: F401
from app.modules.enrollment.models import Class, Enrollment, NodeProgress
from app.modules.iam import models as _iam_models  # noqa: F401
from app.modules.iam.models import (
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserRole,
)
from app.modules.iam.permissions import PERMISSIONS, ROLE_PERMISSIONS, ROLES
from app.modules.integrations import models as _integrations_models  # noqa: F401
from app.modules.notifications import models as _notifications_models  # noqa: F401
from app.modules.projects import models as _projects_models  # noqa: F401
from app.modules.stages import models as _stages_models  # noqa: F401

DEMO_PASSWORD = "pass"
TENANT_SLUG = "the-code"

# Stable identity for the idempotent Blueprint demo course.
DEMO_COURSE_CODE = "MAESTRO-101"


def _now() -> datetime:
    return datetime.now(UTC)

# (username, display name, role key, is_superuser)
DEMO_USERS = [
    ("super", "Super Admin", "super_admin", True),
    ("admin", "Institution Admin", "institution_admin", False),
    ("designer", "Course Designer", "course_designer", False),
    ("teacher", "Teacher One", "teacher", False),
    ("learner", "Learner One", "learner", False),
]

# Older demo identities to remove so login stays simple.
LEGACY_DEMO_EMAILS = [
    "super@the-code.dev",
    "admin@the-code.dev",
    "designer@the-code.dev",
    "teacher@the-code.dev",
    "learner@the-code.dev",
]


async def seed() -> None:
    async with SessionLocal() as session:
        # ── Tenant ──────────────────────────────────────────────────────
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        ).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name="The-Code Demo Institution", slug=TENANT_SLUG)
            session.add(tenant)
            await session.flush()
            print(f"+ tenant {TENANT_SLUG}")

        # ── Permissions ─────────────────────────────────────────────────
        existing_perms = {
            p.key: p for p in (await session.execute(select(Permission))).scalars().all()
        }
        for key, desc in PERMISSIONS.items():
            if key not in existing_perms:
                perm = Permission(key=key, description=desc)
                session.add(perm)
                existing_perms[key] = perm
                print(f"+ permission {key}")
        await session.flush()

        # ── Roles + grants ──────────────────────────────────────────────
        existing_roles = {
            r.key: r
            for r in (await session.execute(select(Role).where(Role.tenant_id == tenant.id)))
            .scalars()
            .all()
        }
        for key, label in ROLES.items():
            role = existing_roles.get(key)
            if role is None:
                role = Role(tenant_id=tenant.id, key=key, name=label)
                session.add(role)
                await session.flush()
                existing_roles[key] = role
                print(f"+ role {key}")

            # Sync this role's permission grants.
            granted = {
                rp.permission_id
                for rp in (
                    await session.execute(
                        select(RolePermission).where(RolePermission.role_id == role.id)
                    )
                )
                .scalars()
                .all()
            }
            for perm_key in ROLE_PERMISSIONS.get(key, []):
                perm = existing_perms[perm_key]
                if perm.id not in granted:
                    session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        await session.flush()

        # ── Remove legacy email-based demo users ─────────────────────────
        legacy_ids = (
            (
                await session.execute(
                    select(User.id).where(
                        User.tenant_id == tenant.id, User.email.in_(LEGACY_DEMO_EMAILS)
                    )
                )
            )
            .scalars()
            .all()
        )
        if legacy_ids:
            await session.execute(delete(UserRole).where(UserRole.user_id.in_(legacy_ids)))
            await session.execute(delete(User).where(User.id.in_(legacy_ids)))
            await session.flush()
            print(f"- removed {len(legacy_ids)} legacy demo user(s)")

        # ── Demo users ──────────────────────────────────────────────────
        for email, name, role_key, is_super in DEMO_USERS:
            user = (
                await session.execute(
                    select(User).where(User.tenant_id == tenant.id, User.email == email)
                )
            ).scalar_one_or_none()
            if user is None:
                user = User(
                    tenant_id=tenant.id,
                    email=email,
                    display_name=name,
                    password_hash=hash_password(DEMO_PASSWORD),
                    is_superuser=is_super,
                )
                session.add(user)
                await session.flush()
                print(f"+ user {email}")
            else:
                # Keep the demo password in sync with DEMO_PASSWORD.
                user.password_hash = hash_password(DEMO_PASSWORD)

            role = existing_roles[role_key]
            has_role = (
                await session.execute(
                    select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
                )
            ).scalar_one_or_none()
            if has_role is None:
                session.add(UserRole(user_id=user.id, role_id=role.id))

        # ── Blueprint-ready demo course ─────────────────────────────────
        users_by_email = {
            u.email: u
            for u in (
                await session.execute(select(User).where(User.tenant_id == tenant.id))
            )
            .scalars()
            .all()
        }
        await _seed_blueprint_course(session, tenant, users_by_email)

        await session.commit()
        print("seed complete.")

    await engine.dispose()


async def _seed_blueprint_course(session, tenant, users_by_email) -> None:
    """Seed one fully Blueprint-ready course (idempotent on ``DEMO_COURSE_CODE``).

    Creates the whole vertical slice the new UI surfaces consume: refined CLOs, a
    published learning-node graph (with ``blueprint_key`` node metadata + edges),
    subtopics, an approved contribution-assessment blueprint, approved design
    artifacts (CLO review + analytics), a class, and a learner enrollment with
    seeded node progress / readiness states.
    """

    existing = (
        await session.execute(
            select(Course).where(
                Course.tenant_id == tenant.id, Course.course_code == DEMO_COURSE_CODE
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return  # already seeded — keep idempotent

    designer = users_by_email.get("designer")
    teacher = users_by_email.get("teacher")
    learner = users_by_email.get("learner")
    if not (designer and teacher and learner):
        print("! skipped blueprint course (demo users missing)")
        return

    designer_id = designer.id

    # ── Course + published version ───────────────────────────────────────
    course = Course(
        tenant_id=tenant.id,
        created_by=designer_id,
        title="Adaptive Curriculum Design Studio",
        description=(
            "A Blueprint-native course: learners re-engineer a curriculum artifact, "
            "demonstrate mastery through node evidence, and ship a verified contribution."
        ),
        status="published",
        course_code=DEMO_COURSE_CODE,
        credit_hours=3,
    )
    session.add(course)
    await session.flush()

    version = CourseVersion(
        course_id=course.id,
        created_by=designer_id,
        version=1,
        state="published",
        published_at=_now(),
    )
    session.add(version)
    await session.flush()

    # ── Refined CLOs ─────────────────────────────────────────────────────
    clo_specs = [
        (
            "CLO-1",
            "Analyze a curriculum framework and justify design trade-offs with evidence.",
            "Understand curriculum frameworks.",
            "Analyze",
        ),
        (
            "CLO-2",
            "Design an adaptive learning sequence that maps outcomes to mastery evidence.",
            "Create a learning sequence.",
            "Create",
        ),
        (
            "CLO-3",
            "Evaluate a contribution against rubric criteria and integrity expectations.",
            "Evaluate student work.",
            "Evaluate",
        ),
    ]
    for position, (code, statement, original, bloom) in enumerate(clo_specs):
        session.add(
            LearningOutcome(
                tenant_id=tenant.id,
                course_id=course.id,
                kind="CLO",
                code=code,
                statement=statement,
                attributes={
                    "refined": True,
                    "original_statement": original,
                    "bloom_level": bloom,
                    "measurable": True,
                    "evidence_of_mastery": "Annotated artifact + decision rationale.",
                },
                position=position,
            )
        )

    # ── Subtopics (Stage 6) ──────────────────────────────────────────────
    subtopic_specs = [
        ("st-frameworks", "CLO-1", "Curriculum Frameworks in Practice", "explore"),
        ("st-sequencing", "CLO-2", "Outcome-to-Evidence Sequencing", "build"),
        ("st-assessment", "CLO-3", "Contribution Assessment & Integrity", "apply"),
    ]
    for position, (key, clo_code, title, fn) in enumerate(subtopic_specs):
        session.add(
            CourseSubtopic(
                tenant_id=tenant.id,
                created_by=designer_id,
                course_id=course.id,
                course_version_id=version.id,
                subtopic_key=key,
                clo_code=clo_code,
                title=title,
                purpose=f"Self-paced territory supporting {clo_code}.",
                learning_function=fn,
                position=position,
            )
        )

    # ── Learning-node graph (with blueprint_key metadata) ────────────────
    node_specs = [
        ("n1", "Foundations of Adaptive Design", "concept"),
        ("n2", "Mapping Outcomes to Evidence", "concept"),
        ("n3", "Designing a Contribution Task", "skill"),
        ("n4", "Capstone Readiness Checkpoint", "mastery_checkpoint"),
    ]
    nodes: dict[str, LearningNode] = {}
    for index, (key, title, node_type) in enumerate(node_specs):
        node = LearningNode(
            course_version_id=version.id,
            type=node_type,
            title=title,
            learning_objective={"summary": f"Demonstrate competence in {title.lower()}."},
            mastery_rule={"requires": ["reflection", "decision_rationale"]},
            completion_rule={"evidence_min": 1},
            node_metadata={"blueprint_key": key, "position": {"x": index * 220, "y": 0}},
        )
        session.add(node)
        nodes[key] = node
    await session.flush()

    edges = [
        ("n1", "n2", "requires"),
        ("n2", "n3", "requires"),
        ("n3", "n4", "mastery_gate"),
    ]
    for source, target, dep_type in edges:
        session.add(
            NodeDependency(
                source_node_id=nodes[source].id,
                target_node_id=nodes[target].id,
                dependency_type=dep_type,
            )
        )

    # ── Approved contribution-assessment blueprint ───────────────────────
    assessment = ContributionAssessment(
        tenant_id=tenant.id,
        created_by=designer_id,
        course_id=course.id,
        course_version_id=version.id,
        assessment_key="capstone-contribution",
        title="Capstone Contribution Project",
        original_title="Final Exam",
        contribution_purpose=(
            "Produce a reusable curriculum-design artifact that could help a real teaching team."
        ),
        clo_codes=["CLO-1", "CLO-2", "CLO-3"],
        fixed_core={
            "deliverable": "A redesigned course module with an evidence map.",
            "constraints": ["cite sources", "disclose AI use"],
        },
        personalized_variables=[
            {"key": "domain", "label": "Discipline / domain", "type": "text"},
            {"key": "audience", "label": "Target learner audience", "type": "text"},
        ],
        required_artifact="Module redesign document + evidence map + reflection.",
        output_formats=["document", "slide_deck"],
        rubric={
            "criteria": [
                {"key": "analysis", "label": "Analytical depth", "weight": 0.4},
                {"key": "design", "label": "Design coherence", "weight": 0.4},
                {"key": "integrity", "label": "Process & integrity", "weight": 0.2},
            ]
        },
        weight=0.4,
        integrity_requirements={
            "ai_use_disclosure": True,
            "process_checkpoints": ["outline", "draft", "final"],
        },
        context_profile_schema={
            "fields": [
                {"key": "domain", "required": True},
                {"key": "audience", "required": True},
            ]
        },
        readiness_gate={"required_node_keys": ["n1", "n2", "n3"]},
        publication_potential="high",
        position=0,
        status="approved",
    )
    session.add(assessment)

    # ── Approved design artifacts (Studio / SME + analytics surfaces) ────
    session.add(
        CourseDesignArtifact(
            tenant_id=tenant.id,
            created_by=designer_id,
            course_id=course.id,
            course_version_id=version.id,
            stage_key="clo_review",
            review_status="approved",
            artifact={
                "clos": [
                    {"code": code, "statement": statement, "bloom_level": bloom}
                    for code, statement, _orig, bloom in clo_specs
                ],
                "gaps": [],
            },
        )
    )
    session.add(
        CourseDesignArtifact(
            tenant_id=tenant.id,
            created_by=designer_id,
            course_id=course.id,
            course_version_id=version.id,
            stage_key="analytics",
            review_status="approved",
            artifact={
                "continuous_improvement": {
                    "recommendations": [
                        "Add a worked example to node n2 (mapping outcomes to evidence).",
                        "Clarify the AI-use disclosure expectations in the capstone rubric.",
                    ],
                    "watch": ["n3 friction: learners stall before the contribution task"],
                }
            },
        )
    )

    # ── Class + learner enrollment + node progress ───────────────────────
    klass = Class(
        tenant_id=tenant.id,
        course_id=course.id,
        teacher_id=teacher.id,
        name="MAESTRO-101 · Section 1",
    )
    session.add(klass)
    await session.flush()

    enrollment = Enrollment(
        tenant_id=tenant.id,
        user_id=learner.id,
        class_id=klass.id,
        course_version_id=version.id,
        status="active",
    )
    session.add(enrollment)
    await session.flush()

    # A realistic in-progress journey: first two nodes done, third in progress.
    progress_specs = [
        ("n1", "completed", "ready"),
        ("n2", "completed", "ready"),
        ("n3", "available", "partially_ready"),
        ("n4", "locked", None),
    ]
    for key, state, readiness in progress_specs:
        session.add(
            NodeProgress(
                enrollment_id=enrollment.id,
                node_id=nodes[key].id,
                state=state,
                readiness_state=readiness,
            )
        )

    print(f"+ blueprint course {DEMO_COURSE_CODE} (4 nodes, 1 assessment, 1 enrollment)")


if __name__ == "__main__":
    asyncio.run(seed())
