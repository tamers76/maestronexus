"""End-to-end integration tests for the Maestro Blueprint learner/faculty runtime.

These exercise the HTTP surface mounted under ``/api/v1/blueprint`` against the
dev Postgres (they **skip** if the database is unavailable, mirroring
``blueprint_test.py``). Each test builds a fully isolated world (its own tenant,
RBAC roles, learner/faculty/SME users, published course + node graph, class,
enrollment, and an approved contribution-assessment blueprint) and tears it down
afterwards, so they never collide with seeded data or each other.

Three Blueprint workflows the unit/promotion tests don't cover:

* **Assessment lifecycle** — node evidence + readiness gate -> formal submission
  -> faculty evaluation -> revision -> resubmission -> grade finalization.
* **Contribution pathway** — prepare a contribution version from a graded
  submission -> SME verification -> faculty publication-candidate listing.
* **Mastery Credit ledger** — faculty award (recommended) -> SME approve ->
  faculty redeem, including the guard that unapproved credits can't be redeemed.

    cd backend; uv run pytest tests/blueprint_runtime_test.py
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal, engine
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.blueprint.models import (
    AssessmentContextProfile,
    AssessmentEvaluation,
    AssessmentSubmission,
    ContributionAssessment,
    ContributionVersion,
    MasteryCredit,
    NodeEvidence,
)
from app.modules.courses.models import Course, CourseVersion, LearningNode
from app.modules.enrollment.models import Class, Enrollment, NodeProgress
from app.modules.iam.models import (
    AuditLog,
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserRole,
)

API = "/api/v1"

LEARNER_PERMS = ["node.progress"]
FACULTY_PERMS = ["project.grade", "report.view_class"]
SME_PERMS = ["stage.review", "course.manage"]
ALL_PERMS = sorted({*LEARNER_PERMS, *FACULTY_PERMS, *SME_PERMS})


@dataclass
class BPWorld:
    tenant_id: uuid.UUID
    course_id: uuid.UUID
    version_id: uuid.UUID
    node_id: uuid.UUID
    enrollment_id: uuid.UUID
    assessment_id: uuid.UUID
    learner_id: uuid.UUID
    faculty_id: uuid.UUID
    sme_id: uuid.UUID
    learner_token: str
    faculty_token: str
    sme_token: str
    role_ids: list[uuid.UUID]
    user_ids: list[uuid.UUID]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _ensure_permissions(session) -> dict[str, Permission]:
    existing = {
        p.key: p
        for p in (
            await session.execute(select(Permission).where(Permission.key.in_(ALL_PERMS)))
        )
        .scalars()
        .all()
    }
    for key in ALL_PERMS:
        if key not in existing:
            perm = Permission(key=key, description=f"test {key}")
            session.add(perm)
            await session.flush()
            existing[key] = perm
    return existing


async def _make_user(session, tenant_id, role_id, label) -> uuid.UUID:
    user = User(
        tenant_id=tenant_id,
        email=f"{label}-{uuid.uuid4().hex[:8]}@test.dev",
        display_name=label,
        password_hash=hash_password("x"),
        status="active",
        is_superuser=False,
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=role_id))
    return user.id


@pytest_asyncio.fixture
async def bp_world() -> AsyncIterator[BPWorld]:
    # Skip cleanly if the dev Postgres isn't reachable.
    await engine.dispose()
    try:
        async with SessionLocal() as probe:
            await probe.execute(select(1))
    except Exception:  # noqa: BLE001 - any connection error -> skip
        pytest.skip("dev Postgres unavailable")

    async with SessionLocal() as session:
        perms = await _ensure_permissions(session)

        tenant = Tenant(name="BP Runtime", slug=f"bpr-{uuid.uuid4().hex[:10]}")
        session.add(tenant)
        await session.flush()

        learner_role = Role(tenant_id=tenant.id, key="bpr_learner", name="BPR Learner")
        faculty_role = Role(tenant_id=tenant.id, key="bpr_faculty", name="BPR Faculty")
        sme_role = Role(tenant_id=tenant.id, key="bpr_sme", name="BPR SME")
        session.add_all([learner_role, faculty_role, sme_role])
        await session.flush()
        for key in LEARNER_PERMS:
            session.add(RolePermission(role_id=learner_role.id, permission_id=perms[key].id))
        for key in FACULTY_PERMS:
            session.add(RolePermission(role_id=faculty_role.id, permission_id=perms[key].id))
        for key in SME_PERMS:
            session.add(RolePermission(role_id=sme_role.id, permission_id=perms[key].id))

        learner_id = await _make_user(session, tenant.id, learner_role.id, "learner")
        faculty_id = await _make_user(session, tenant.id, faculty_role.id, "faculty")
        sme_id = await _make_user(session, tenant.id, sme_role.id, "sme")

        course = Course(tenant_id=tenant.id, title="Blueprint Course", status="published")
        session.add(course)
        await session.flush()
        version = CourseVersion(course_id=course.id, version=1, state="published")
        session.add(version)
        await session.flush()
        node = LearningNode(
            course_version_id=version.id,
            type="mastery_node",
            title="Core Mastery Node",
            node_metadata={"blueprint_key": "n1"},
        )
        session.add(node)
        await session.flush()

        klass = Class(
            tenant_id=tenant.id, course_id=course.id, teacher_id=faculty_id, name="Section 1"
        )
        session.add(klass)
        await session.flush()
        enrollment = Enrollment(
            tenant_id=tenant.id,
            user_id=learner_id,
            class_id=klass.id,
            course_version_id=version.id,
            status="active",
        )
        session.add(enrollment)
        await session.flush()
        # The readiness gate mirrors evidence onto an existing progress row.
        session.add(
            NodeProgress(enrollment_id=enrollment.id, node_id=node.id, state="available")
        )

        assessment = ContributionAssessment(
            tenant_id=tenant.id,
            course_id=course.id,
            course_version_id=version.id,
            assessment_key="a1",
            title="Capstone Contribution",
            clo_codes=["CLO-1"],
            rubric={"criteria": [{"key": "analysis", "weight": 1.0}]},
            readiness_gate={"required_node_keys": ["n1"]},
            status="approved",
            position=0,
        )
        session.add(assessment)
        await session.flush()

        w = BPWorld(
            tenant_id=tenant.id,
            course_id=course.id,
            version_id=version.id,
            node_id=node.id,
            enrollment_id=enrollment.id,
            assessment_id=assessment.id,
            learner_id=learner_id,
            faculty_id=faculty_id,
            sme_id=sme_id,
            learner_token=create_access_token(learner_id, tenant.id),
            faculty_token=create_access_token(faculty_id, tenant.id),
            sme_token=create_access_token(sme_id, tenant.id),
            role_ids=[learner_role.id, faculty_role.id, sme_role.id],
            user_ids=[learner_id, faculty_id, sme_id],
        )
        await session.commit()

    try:
        yield w
    finally:
        await _teardown(w)


async def _teardown(w: BPWorld) -> None:
    async with SessionLocal() as session:
        # Enrollment / course cascades cover most children; delete explicitly to
        # be order-independent and clear the audit trail this tenant created.
        await session.execute(
            delete(AssessmentEvaluation).where(
                AssessmentEvaluation.submission_id.in_(
                    select(AssessmentSubmission.id).where(
                        AssessmentSubmission.enrollment_id == w.enrollment_id
                    )
                )
            )
        )
        await session.execute(
            delete(ContributionVersion).where(
                ContributionVersion.enrollment_id == w.enrollment_id
            )
        )
        await session.execute(
            delete(MasteryCredit).where(MasteryCredit.enrollment_id == w.enrollment_id)
        )
        await session.execute(
            delete(AssessmentSubmission).where(
                AssessmentSubmission.enrollment_id == w.enrollment_id
            )
        )
        await session.execute(
            delete(AssessmentContextProfile).where(
                AssessmentContextProfile.enrollment_id == w.enrollment_id
            )
        )
        await session.execute(
            delete(NodeEvidence).where(NodeEvidence.enrollment_id == w.enrollment_id)
        )
        await session.execute(
            delete(ContributionAssessment).where(
                ContributionAssessment.course_id == w.course_id
            )
        )
        await session.execute(
            delete(NodeProgress).where(NodeProgress.enrollment_id == w.enrollment_id)
        )
        await session.execute(delete(Enrollment).where(Enrollment.id == w.enrollment_id))
        await session.execute(delete(Class).where(Class.tenant_id == w.tenant_id))
        await session.execute(delete(LearningNode).where(LearningNode.id == w.node_id))
        await session.execute(delete(CourseVersion).where(CourseVersion.id == w.version_id))
        await session.execute(delete(Course).where(Course.id == w.course_id))
        await session.execute(delete(AuditLog).where(AuditLog.tenant_id == w.tenant_id))
        await session.execute(delete(UserRole).where(UserRole.user_id.in_(w.user_ids)))
        await session.execute(delete(User).where(User.id.in_(w.user_ids)))
        await session.execute(delete(RolePermission).where(RolePermission.role_id.in_(w.role_ids)))
        await session.execute(delete(Role).where(Role.id.in_(w.role_ids)))
        await session.execute(delete(Tenant).where(Tenant.id == w.tenant_id))
        await session.commit()
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Workflow 1: readiness -> submission -> evaluation -> revision -> grade ─────


async def test_assessment_readiness_submission_evaluation_revision_grade(
    client: AsyncClient, bp_world: BPWorld
):
    w = bp_world
    learner = _auth(w.learner_token)
    faculty = _auth(w.faculty_token)

    # Before any evidence the gate is closed (node not ready + no context).
    res = await client.get(
        f"{API}/blueprint/assessments/{w.assessment_id}/readiness",
        headers=learner,
        params={"enrollment_id": str(w.enrollment_id)},
    )
    assert res.status_code == 200, res.text
    assert res.json()["outcome"] == "not_ready"

    # 1. Learner submits node evidence; reflection + rationale -> "ready".
    res = await client.post(
        f"{API}/blueprint/enrollments/{w.enrollment_id}/nodes/{w.node_id}/evidence",
        headers=learner,
        json={
            "evidence": {
                "reflection": "I compared three framings and justified my choice.",
                "decision_rationale": "Chose framing B for its measurable criteria.",
            }
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["readiness_state"] == "ready"
    assert body["ai_companion_message"]

    # 2. Learner submits a context profile; faculty approves it.
    res = await client.post(
        f"{API}/blueprint/assessments/{w.assessment_id}/context-profile",
        headers=learner,
        json={"enrollment_id": str(w.enrollment_id), "profile": {"domain": "healthcare"}},
    )
    assert res.status_code == 200, res.text
    profile_id = res.json()["id"]
    assert res.json()["status"] == "submitted"

    res = await client.post(
        f"{API}/blueprint/context-profiles/{profile_id}/review",
        headers=faculty,
        json={"approve": True, "note": "Scope is appropriate."},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"

    # 3. Gate now opens.
    res = await client.get(
        f"{API}/blueprint/assessments/{w.assessment_id}/readiness",
        headers=learner,
        params={"enrollment_id": str(w.enrollment_id)},
    )
    assert res.status_code == 200, res.text
    gate = res.json()
    assert gate["outcome"] == "ready_to_submit"
    assert gate["missing_node_keys"] == []
    assert gate["context_profile_approved"] is True

    # 4. Learner files a formal submission.
    res = await client.post(
        f"{API}/blueprint/assessments/{w.assessment_id}/submissions",
        headers=learner,
        json={
            "enrollment_id": str(w.enrollment_id),
            "package": {"artifact": "v1 analysis", "ai_use_disclosure": "Used AI for outline."},
            "submit": True,
        },
    )
    assert res.status_code == 200, res.text
    submission = res.json()
    submission_id = submission["id"]
    assert submission["status"] == "submitted"
    assert submission["version"] == 1
    assert submission["context_profile_id"] == profile_id

    # 5. Faculty evaluates and requests a minor revision.
    res = await client.post(
        f"{API}/blueprint/submissions/{submission_id}/evaluate",
        headers=faculty,
        json={
            "rubric_scores": {"analysis": 3},
            "recommendation": "minor_revision",
            "feedback_learner": "Tighten the evidence section.",
            "evaluator_kind": "sme",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["recommendation"] == "minor_revision"

    res = await client.post(
        f"{API}/blueprint/submissions/{submission_id}/request-revision",
        headers=faculty,
        json={"kind": "minor", "note": "Add the missing citations."},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "revision_requested"

    # 6. Learner revises the (now editable) submission and re-submits.
    res = await client.patch(
        f"{API}/blueprint/submissions/{submission_id}",
        headers=learner,
        json={"package": {"artifact": "v2 analysis with citations"}},
    )
    assert res.status_code == 200, res.text

    res = await client.post(
        f"{API}/blueprint/submissions/{submission_id}/submit", headers=learner
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "submitted"

    # 7. Faculty re-evaluates (accept) and finalizes the grade.
    res = await client.post(
        f"{API}/blueprint/submissions/{submission_id}/evaluate",
        headers=faculty,
        json={"rubric_scores": {"analysis": 5}, "recommendation": "accept"},
    )
    assert res.status_code == 200, res.text

    res = await client.post(
        f"{API}/blueprint/submissions/{submission_id}/finalize-grade",
        headers=faculty,
        json={"grade": 92.5, "feedback_learner": "Strong work.", "publication_potential": "high"},
    )
    assert res.status_code == 200, res.text
    final_eval = res.json()
    assert final_eval["finalized"] is True
    assert final_eval["grade"] == 92.5

    res = await client.get(f"{API}/blueprint/submissions/{submission_id}", headers=learner)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "graded"

    # Faculty analytics reflect the graded submission + readiness state.
    res = await client.get(
        f"{API}/blueprint/courses/{w.course_id}/analytics", headers=faculty
    )
    assert res.status_code == 200, res.text
    analytics = res.json()
    assert analytics["submissions_by_status"].get("graded") == 1
    assert analytics["readiness_states"].get("ready") == 1
    assert analytics["evaluations"]["finalized"] == 1


# ── Workflow 2: contribution preparation -> SME verification ───────────────────


async def test_contribution_preparation_and_sme_verification(
    client: AsyncClient, bp_world: BPWorld
):
    w = bp_world
    learner = _auth(w.learner_token)
    sme = _auth(w.sme_token)
    faculty = _auth(w.faculty_token)

    # A submitted package is the seed for a contribution version.
    res = await client.post(
        f"{API}/blueprint/assessments/{w.assessment_id}/submissions",
        headers=learner,
        json={
            "enrollment_id": str(w.enrollment_id),
            "package": {"artifact": "publishable case study"},
            "submit": True,
        },
    )
    assert res.status_code == 200, res.text
    submission_id = res.json()["id"]

    # Learner prepares a contribution version (consent + anonymized).
    res = await client.post(
        f"{API}/blueprint/submissions/{submission_id}/contribution",
        headers=learner,
        json={
            "format": "case_study",
            "title": "Adaptive Triage in Rural Clinics",
            "summary": "A reusable decision framework.",
            "body": {"sections": ["context", "method", "results"]},
            "consent": True,
            "anonymized": True,
            "visibility_level": "internal",
            "license": "CC-BY-4.0",
        },
    )
    assert res.status_code == 200, res.text
    contribution = res.json()
    contribution_id = contribution["id"]
    assert contribution["verification_status"] == "pending"
    assert contribution["consent"] is True

    # SME verifies it and promotes visibility to public.
    res = await client.post(
        f"{API}/blueprint/contributions/{contribution_id}/verify",
        headers=sme,
        json={
            "verification_status": "verified",
            "visibility_level": "public",
            "note": "Anonymization confirmed; strong contribution.",
        },
    )
    assert res.status_code == 200, res.text
    verified = res.json()
    assert verified["verification_status"] == "verified"
    assert verified["visibility_level"] == "public"
    assert verified["verified_by"] == str(w.sme_id)
    assert verified["metadata"].get("verification_note")

    # It surfaces to the learner's own list and to faculty publication candidates.
    res = await client.get(
        f"{API}/blueprint/enrollments/{w.enrollment_id}/contributions", headers=learner
    )
    assert res.status_code == 200, res.text
    assert any(c["id"] == contribution_id for c in res.json())

    res = await client.get(
        f"{API}/blueprint/courses/{w.course_id}/contributions", headers=faculty
    )
    assert res.status_code == 200, res.text
    assert any(c["id"] == contribution_id for c in res.json())


# ── Workflow 3: Mastery Credit award -> approve -> redeem ──────────────────────


async def test_mastery_credit_award_approve_redeem(client: AsyncClient, bp_world: BPWorld):
    w = bp_world
    learner = _auth(w.learner_token)
    faculty = _auth(w.faculty_token)
    sme = _auth(w.sme_token)

    # Faculty recommends a credit.
    res = await client.post(
        f"{API}/blueprint/enrollments/{w.enrollment_id}/credits",
        headers=faculty,
        json={
            "source_type": "assessment",
            "source_id": str(w.assessment_id),
            "amount": 1.5,
            "rationale": "Exceptional, publishable contribution.",
        },
    )
    assert res.status_code == 200, res.text
    credit = res.json()
    credit_id = credit["id"]
    assert credit["status"] == "recommended"
    assert credit["amount"] == 1.5

    # Unapproved credits can't be redeemed yet (409 guard).
    res = await client.post(
        f"{API}/blueprint/credits/{credit_id}/redeem",
        headers=faculty,
        json={"redeemed_for": "elective_waiver"},
    )
    assert res.status_code == 409, res.text

    # SME approves the credit.
    res = await client.post(f"{API}/blueprint/credits/{credit_id}/approve", headers=sme)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"
    assert res.json()["approved_by"] == str(w.sme_id)

    # Faculty redeems the approved credit.
    res = await client.post(
        f"{API}/blueprint/credits/{credit_id}/redeem",
        headers=faculty,
        json={"redeemed_for": "elective_waiver"},
    )
    assert res.status_code == 200, res.text
    redeemed = res.json()
    assert redeemed["status"] == "redeemed"
    assert redeemed["redeemed_for"] == "elective_waiver"

    # Learner sees the credit in their ledger.
    res = await client.get(
        f"{API}/blueprint/enrollments/{w.enrollment_id}/credits", headers=learner
    )
    assert res.status_code == 200, res.text
    ledger = res.json()
    assert len(ledger) == 1
    assert ledger[0]["status"] == "redeemed"
