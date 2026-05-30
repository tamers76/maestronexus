"""Maestro Blueprint runtime service (learner + faculty workflows).

Business logic kept out of the router. Tenant isolation is enforced by resolving
ownership back to ``Course.tenant_id`` / ``Enrollment.tenant_id`` and, for learner
actions, by checking ``Enrollment.user_id == caller``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Principal, ensure_same_tenant
from app.modules.blueprint.models import (
    AssessmentContextProfile,
    AssessmentEvaluation,
    AssessmentSubmission,
    ContributionAssessment,
    ContributionVersion,
    CourseDesignArtifact,
    MasteryCredit,
    NodeEvidence,
)
from app.modules.courses.models import Course, CourseVersion, LearningNode
from app.modules.enrollment.models import Enrollment, NodeProgress

_READY_PROGRESS_STATES = ("completed", "mastered")
_READY_READINESS = ("ready", "advanced")


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


# ── Loaders ─────────────────────────────────────────────────────────────────


async def _load_course(session: AsyncSession, user: Principal, course_id: uuid.UUID) -> Course:
    course = await session.get(Course, course_id)
    if course is None:
        raise _not_found("Course")
    ensure_same_tenant(user, course.tenant_id)
    return course


async def load_assessment(
    session: AsyncSession, user: Principal, assessment_id: uuid.UUID
) -> ContributionAssessment:
    row = await session.get(ContributionAssessment, assessment_id)
    if row is None:
        raise _not_found("Contribution assessment")
    ensure_same_tenant(user, row.tenant_id)
    return row


async def load_enrollment(
    session: AsyncSession, user: Principal, enrollment_id: uuid.UUID
) -> Enrollment:
    row = await session.get(Enrollment, enrollment_id)
    if row is None or row.deleted_at is not None:
        raise _not_found("Enrollment")
    ensure_same_tenant(user, row.tenant_id)
    return row


def _require_owner(user: Principal, enrollment: Enrollment) -> None:
    if enrollment.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only act on your own enrollment",
        )


async def load_submission(
    session: AsyncSession, user: Principal, submission_id: uuid.UUID
) -> AssessmentSubmission:
    row = await session.get(AssessmentSubmission, submission_id)
    if row is None:
        raise _not_found("Submission")
    ensure_same_tenant(user, row.tenant_id)
    return row


async def load_contribution(
    session: AsyncSession, user: Principal, contribution_id: uuid.UUID
) -> ContributionVersion:
    row = await session.get(ContributionVersion, contribution_id)
    if row is None:
        raise _not_found("Contribution version")
    ensure_same_tenant(user, row.tenant_id)
    return row


async def load_credit(
    session: AsyncSession, user: Principal, credit_id: uuid.UUID
) -> MasteryCredit:
    row = await session.get(MasteryCredit, credit_id)
    if row is None:
        raise _not_found("Mastery credit")
    ensure_same_tenant(user, row.tenant_id)
    return row


# ── Contribution assessments (design / SME) ───────────────────────────────────


async def list_assessments(
    session: AsyncSession, user: Principal, course_id: uuid.UUID
) -> list[ContributionAssessment]:
    await _load_course(session, user, course_id)
    rows = (
        (
            await session.execute(
                select(ContributionAssessment)
                .where(ContributionAssessment.course_id == course_id)
                .order_by(ContributionAssessment.position.asc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def update_assessment(
    session: AsyncSession, user: Principal, assessment_id: uuid.UUID, data: dict
) -> ContributionAssessment:
    row = await load_assessment(session, user, assessment_id)
    for field, value in data.items():
        setattr(row, field, value)
    await session.flush()
    await session.refresh(row)
    return row


async def approve_assessment(
    session: AsyncSession, user: Principal, assessment_id: uuid.UUID
) -> ContributionAssessment:
    row = await load_assessment(session, user, assessment_id)
    row.status = "approved"
    await session.flush()
    await session.refresh(row)
    return row


# ── Context profile ────────────────────────────────────────────────────────────


async def submit_context_profile(
    session: AsyncSession,
    user: Principal,
    assessment_id: uuid.UUID,
    *,
    enrollment_id: uuid.UUID,
    profile: dict,
) -> AssessmentContextProfile:
    assessment = await load_assessment(session, user, assessment_id)
    enrollment = await load_enrollment(session, user, enrollment_id)
    _require_owner(user, enrollment)

    row = (
        await session.execute(
            select(AssessmentContextProfile).where(
                AssessmentContextProfile.assessment_id == assessment.id,
                AssessmentContextProfile.enrollment_id == enrollment.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = AssessmentContextProfile(
            tenant_id=enrollment.tenant_id,
            assessment_id=assessment.id,
            enrollment_id=enrollment.id,
            profile=profile,
            status="submitted",
        )
        session.add(row)
    else:
        row.profile = profile
        row.status = "submitted"
        row.reviewed_by = None
        row.review_note = None
    await session.flush()
    await session.refresh(row)
    return row


async def review_context_profile(
    session: AsyncSession,
    user: Principal,
    profile_id: uuid.UUID,
    *,
    approve: bool,
    note: str | None,
) -> AssessmentContextProfile:
    row = await session.get(AssessmentContextProfile, profile_id)
    if row is None:
        raise _not_found("Context profile")
    ensure_same_tenant(user, row.tenant_id)
    row.status = "approved" if approve else "rejected"
    row.reviewed_by = user.id
    row.review_note = note
    await session.flush()
    await session.refresh(row)
    return row


# ── Node evidence + readiness ─────────────────────────────────────────────────


def _derive_readiness(evidence: dict, provided: str | None) -> str:
    if provided in ("not_ready", "partially_ready", "ready", "advanced"):
        return provided
    if not evidence:
        return "not_ready"
    # Heuristic: richer evidence (reflection + decision rationale) signals more
    # readiness; an SME/AI evaluation can override this later.
    has_reflection = bool(evidence.get("reflection"))
    has_decision = bool(evidence.get("decision_rationale") or evidence.get("decision_log"))
    if has_reflection and has_decision:
        return "ready"
    return "partially_ready"


def _companion_message(node_title: str, state: str) -> str:
    messages = {
        "not_ready": (
            f"Let's build more evidence on “{node_title}”. Try the evidence task "
            "again and show your reasoning."
        ),
        "partially_ready": (
            f"You're close on “{node_title}”. Add your decision rationale and a "
            "short reflection to demonstrate mastery."
        ),
        "ready": f"Nice work — you've demonstrated mastery of “{node_title}”. Ready to move on.",
        "advanced": (
            f"Excellent depth on “{node_title}”. An optional challenge is available "
            "if you want to go further."
        ),
    }
    return messages.get(state, "")


async def submit_node_evidence(
    session: AsyncSession,
    user: Principal,
    enrollment_id: uuid.UUID,
    node_id: uuid.UUID,
    *,
    evidence: dict,
    readiness_state: str | None,
) -> NodeEvidence:
    enrollment = await load_enrollment(session, user, enrollment_id)
    _require_owner(user, enrollment)

    node = await session.get(LearningNode, node_id)
    if node is None or node.course_version_id != enrollment.course_version_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node is not part of this enrollment's course version",
        )

    state = _derive_readiness(evidence, readiness_state)
    message = _companion_message(node.title, state)
    row = NodeEvidence(
        tenant_id=enrollment.tenant_id,
        enrollment_id=enrollment.id,
        node_id=node_id,
        evidence=evidence,
        readiness_state=state,
        feedback={"companion_message": message},
        ai_companion_message=message,
    )
    session.add(row)

    # Mirror the readiness state onto the node-progress row (kept separate from
    # the locked/available/completed traversal state).
    progress = (
        await session.execute(
            select(NodeProgress).where(
                NodeProgress.enrollment_id == enrollment.id,
                NodeProgress.node_id == node_id,
            )
        )
    ).scalar_one_or_none()
    if progress is not None:
        progress.readiness_state = state
    await session.flush()
    await session.refresh(row)
    return row


async def list_node_evidence(
    session: AsyncSession, user: Principal, enrollment_id: uuid.UUID, node_id: uuid.UUID
) -> list[NodeEvidence]:
    enrollment = await load_enrollment(session, user, enrollment_id)
    if enrollment.user_id != user.id and not user.has_permission("report.view_class"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires report.view_class to view another learner's evidence",
        )
    rows = (
        (
            await session.execute(
                select(NodeEvidence)
                .where(
                    NodeEvidence.enrollment_id == enrollment_id,
                    NodeEvidence.node_id == node_id,
                )
                .order_by(NodeEvidence.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


# ── Readiness gate ─────────────────────────────────────────────────────────────


async def check_readiness(
    session: AsyncSession, user: Principal, assessment_id: uuid.UUID, enrollment_id: uuid.UUID
) -> dict:
    assessment = await load_assessment(session, user, assessment_id)
    enrollment = await load_enrollment(session, user, enrollment_id)
    if enrollment.user_id != user.id and not user.has_permission("report.view_class"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires report.view_class to view another learner's readiness",
        )

    gate = assessment.readiness_gate or {}
    required_keys = [str(k) for k in (gate.get("required_node_keys") or [])]

    # Resolve required node keys -> nodes in the enrollment's course version.
    nodes = (
        (
            await session.execute(
                select(LearningNode).where(
                    LearningNode.course_version_id == enrollment.course_version_id
                )
            )
        )
        .scalars()
        .all()
    )
    node_by_key = {
        str((n.node_metadata or {}).get("blueprint_key")): n
        for n in nodes
        if (n.node_metadata or {}).get("blueprint_key")
    }
    progress_rows = (
        (
            await session.execute(
                select(NodeProgress).where(NodeProgress.enrollment_id == enrollment.id)
            )
        )
        .scalars()
        .all()
    )
    progress_by_node = {p.node_id: p for p in progress_rows}

    missing: list[str] = []
    for key in required_keys:
        node = node_by_key.get(key)
        if node is None:
            missing.append(key)
            continue
        prog = progress_by_node.get(node.id)
        ready = prog is not None and (
            prog.state in _READY_PROGRESS_STATES
            or prog.readiness_state in _READY_READINESS
        )
        if not ready:
            missing.append(key)

    context = (
        await session.execute(
            select(AssessmentContextProfile).where(
                AssessmentContextProfile.assessment_id == assessment.id,
                AssessmentContextProfile.enrollment_id == enrollment.id,
            )
        )
    ).scalar_one_or_none()
    context_approved = context is not None and context.status == "approved"

    checks = [
        {
            "check": "required_nodes_completed",
            "passed": not missing,
            "detail": None if not missing else f"{len(missing)} required node(s) not ready",
        },
        {
            "check": "context_profile_approved",
            "passed": context_approved,
            "detail": None if context_approved else "Context profile not approved",
        },
    ]
    passed = sum(1 for c in checks if c["passed"])
    if passed == len(checks):
        outcome = "ready_to_submit"
    elif passed == 0:
        outcome = "not_ready"
    else:
        outcome = "needs_targeted_support"

    return {
        "assessment_id": assessment.id,
        "enrollment_id": enrollment.id,
        "outcome": outcome,
        "checks": checks,
        "missing_node_keys": missing,
        "context_profile_approved": context_approved,
    }


# ── Submissions ────────────────────────────────────────────────────────────────


async def create_submission(
    session: AsyncSession,
    user: Principal,
    assessment_id: uuid.UUID,
    *,
    enrollment_id: uuid.UUID,
    package: dict,
    submit: bool,
) -> AssessmentSubmission:
    assessment = await load_assessment(session, user, assessment_id)
    enrollment = await load_enrollment(session, user, enrollment_id)
    _require_owner(user, enrollment)

    context = (
        await session.execute(
            select(AssessmentContextProfile).where(
                AssessmentContextProfile.assessment_id == assessment.id,
                AssessmentContextProfile.enrollment_id == enrollment.id,
            )
        )
    ).scalar_one_or_none()

    prior = (
        await session.execute(
            select(func.count())
            .select_from(AssessmentSubmission)
            .where(
                AssessmentSubmission.assessment_id == assessment.id,
                AssessmentSubmission.enrollment_id == enrollment.id,
            )
        )
    ).scalar_one()

    row = AssessmentSubmission(
        tenant_id=enrollment.tenant_id,
        assessment_id=assessment.id,
        enrollment_id=enrollment.id,
        context_profile_id=context.id if context else None,
        package=package,
        version=int(prior) + 1,
        status="submitted" if submit else "draft",
        submitted_at=datetime.now(UTC) if submit else None,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def update_submission(
    session: AsyncSession, user: Principal, submission_id: uuid.UUID, *, package: dict | None
) -> AssessmentSubmission:
    row = await load_submission(session, user, submission_id)
    enrollment = await load_enrollment(session, user, row.enrollment_id)
    _require_owner(user, enrollment)
    if row.status not in ("draft", "revision_requested"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft or revision-requested submissions can be edited",
        )
    if package is not None:
        row.package = package
    await session.flush()
    await session.refresh(row)
    return row


async def submit_submission(
    session: AsyncSession, user: Principal, submission_id: uuid.UUID
) -> AssessmentSubmission:
    row = await load_submission(session, user, submission_id)
    enrollment = await load_enrollment(session, user, row.enrollment_id)
    _require_owner(user, enrollment)
    row.status = "submitted"
    row.submitted_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(row)
    return row


async def list_submissions(
    session: AsyncSession,
    user: Principal,
    *,
    assessment_id: uuid.UUID | None,
    enrollment_id: uuid.UUID | None,
) -> list[AssessmentSubmission]:
    stmt = select(AssessmentSubmission)
    if assessment_id is not None:
        assessment = await load_assessment(session, user, assessment_id)
        stmt = stmt.where(AssessmentSubmission.assessment_id == assessment.id)
    if enrollment_id is not None:
        enrollment = await load_enrollment(session, user, enrollment_id)
        if enrollment.user_id != user.id and not user.has_permission("report.view_class"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requires report.view_class to view another learner's submissions",
            )
        stmt = stmt.where(AssessmentSubmission.enrollment_id == enrollment.id)
    elif not user.has_permission("report.view_class") and not user.has_permission("project.grade"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provide enrollment_id, or hold report.view_class / project.grade",
        )
    rows = (
        (await session.execute(stmt.order_by(AssessmentSubmission.created_at.desc())))
        .scalars()
        .all()
    )
    return list(rows)


# ── Evaluation / grading ─────────────────────────────────────────────────────


async def evaluate_submission(
    session: AsyncSession, user: Principal, submission_id: uuid.UUID, *, data: dict
) -> AssessmentEvaluation:
    row = await load_submission(session, user, submission_id)
    if row.status == "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Submission is still a draft"
        )
    row.status = "under_review"
    evaluation = AssessmentEvaluation(
        tenant_id=row.tenant_id,
        submission_id=row.id,
        rubric_scores=data.get("rubric_scores") or {},
        recommendation=data.get("recommendation"),
        feedback_learner=data.get("feedback_learner"),
        feedback_sme=data.get("feedback_sme"),
        integrity_flag=bool(data.get("integrity_flag")),
        publication_potential=data.get("publication_potential"),
        grade=data.get("grade"),
        evaluator_kind=data.get("evaluator_kind") or "ai",
        evaluated_by=user.id,
    )
    session.add(evaluation)
    await session.flush()
    await session.refresh(evaluation)
    return evaluation


async def _latest_evaluation(
    session: AsyncSession, submission_id: uuid.UUID
) -> AssessmentEvaluation | None:
    return (
        await session.execute(
            select(AssessmentEvaluation)
            .where(AssessmentEvaluation.submission_id == submission_id)
            .order_by(AssessmentEvaluation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def finalize_grade(
    session: AsyncSession,
    user: Principal,
    submission_id: uuid.UUID,
    *,
    grade: float,
    feedback_learner: str | None,
    publication_potential: str | None,
) -> AssessmentEvaluation:
    row = await load_submission(session, user, submission_id)
    evaluation = await _latest_evaluation(session, submission_id)
    if evaluation is None:
        evaluation = AssessmentEvaluation(
            tenant_id=row.tenant_id, submission_id=row.id, evaluator_kind="sme"
        )
        session.add(evaluation)
    evaluation.grade = grade
    if feedback_learner is not None:
        evaluation.feedback_learner = feedback_learner
    if publication_potential is not None:
        evaluation.publication_potential = publication_potential
    evaluation.finalized = True
    evaluation.evaluator_kind = "sme"
    evaluation.evaluated_by = user.id
    row.status = "graded"
    await session.flush()
    await session.refresh(evaluation)
    return evaluation


async def request_revision(
    session: AsyncSession,
    user: Principal,
    submission_id: uuid.UUID,
    *,
    kind: str,
    note: str | None,
) -> AssessmentSubmission:
    row = await load_submission(session, user, submission_id)
    row.status = "revision_requested"
    evaluation = await _latest_evaluation(session, submission_id)
    if evaluation is None:
        evaluation = AssessmentEvaluation(
            tenant_id=row.tenant_id, submission_id=row.id, evaluator_kind="sme"
        )
        session.add(evaluation)
    evaluation.recommendation = "minor_revision" if kind == "minor" else "major_revision"
    if note is not None:
        evaluation.feedback_learner = note
    evaluation.evaluated_by = user.id
    await session.flush()
    await session.refresh(row)
    return row


async def get_evaluation(
    session: AsyncSession, user: Principal, submission_id: uuid.UUID
) -> AssessmentEvaluation | None:
    await load_submission(session, user, submission_id)
    return await _latest_evaluation(session, submission_id)


# ── Contribution versions ────────────────────────────────────────────────────


async def prepare_contribution(
    session: AsyncSession, user: Principal, submission_id: uuid.UUID, *, data: dict
) -> ContributionVersion:
    submission = await load_submission(session, user, submission_id)
    enrollment = await load_enrollment(session, user, submission.enrollment_id)
    _require_owner(user, enrollment)
    row = ContributionVersion(
        tenant_id=enrollment.tenant_id,
        submission_id=submission.id,
        enrollment_id=enrollment.id,
        format=data.get("format"),
        title=data.get("title"),
        summary=data.get("summary"),
        body=data.get("body") or {},
        contribution_metadata=data.get("metadata") or {},
        consent=bool(data.get("consent")),
        anonymized=bool(data.get("anonymized")),
        visibility_level=data.get("visibility_level") or "private",
        license=data.get("license"),
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def update_contribution(
    session: AsyncSession, user: Principal, contribution_id: uuid.UUID, *, data: dict
) -> ContributionVersion:
    row = await load_contribution(session, user, contribution_id)
    enrollment = await load_enrollment(session, user, row.enrollment_id)
    _require_owner(user, enrollment)
    field_map = {"metadata": "contribution_metadata"}
    for field, value in data.items():
        setattr(row, field_map.get(field, field), value)
    await session.flush()
    await session.refresh(row)
    return row


async def verify_contribution(
    session: AsyncSession,
    user: Principal,
    contribution_id: uuid.UUID,
    *,
    verification_status: str,
    visibility_level: str | None,
    note: str | None,
) -> ContributionVersion:
    row = await load_contribution(session, user, contribution_id)
    row.verification_status = verification_status
    if visibility_level is not None:
        row.visibility_level = visibility_level
    if note is not None:
        meta = dict(row.contribution_metadata or {})
        meta["verification_note"] = note
        row.contribution_metadata = meta
    row.verified_by = user.id
    await session.flush()
    await session.refresh(row)
    return row


async def list_contributions_for_enrollment(
    session: AsyncSession, user: Principal, enrollment_id: uuid.UUID
) -> list[ContributionVersion]:
    enrollment = await load_enrollment(session, user, enrollment_id)
    if enrollment.user_id != user.id and not user.has_permission("report.view_class"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires report.view_class to view another learner's contributions",
        )
    rows = (
        (
            await session.execute(
                select(ContributionVersion)
                .where(ContributionVersion.enrollment_id == enrollment_id)
                .order_by(ContributionVersion.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def list_publication_candidates(
    session: AsyncSession, user: Principal, course_id: uuid.UUID
) -> list[ContributionVersion]:
    await _load_course(session, user, course_id)
    # Contributions whose enrollment pins a version of this course.
    rows = (
        (
            await session.execute(
                select(ContributionVersion)
                .join(Enrollment, Enrollment.id == ContributionVersion.enrollment_id)
                .join(CourseVersion, CourseVersion.id == Enrollment.course_version_id)
                .where(CourseVersion.course_id == course_id)
                .order_by(ContributionVersion.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


# ── Mastery credits ────────────────────────────────────────────────────────────


async def list_credits(
    session: AsyncSession, user: Principal, enrollment_id: uuid.UUID
) -> list[MasteryCredit]:
    enrollment = await load_enrollment(session, user, enrollment_id)
    if enrollment.user_id != user.id and not user.has_permission("report.view_class"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires report.view_class to view another learner's credits",
        )
    rows = (
        (
            await session.execute(
                select(MasteryCredit)
                .where(MasteryCredit.enrollment_id == enrollment_id)
                .order_by(MasteryCredit.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def award_credit(
    session: AsyncSession,
    user: Principal,
    enrollment_id: uuid.UUID,
    *,
    source_type: str,
    source_id: uuid.UUID | None,
    amount: float,
    rationale: str | None,
) -> MasteryCredit:
    enrollment = await load_enrollment(session, user, enrollment_id)
    row = MasteryCredit(
        tenant_id=enrollment.tenant_id,
        enrollment_id=enrollment.id,
        source_type=source_type,
        source_id=source_id,
        amount=amount,
        rationale=rationale,
        status="recommended",
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def approve_credit(
    session: AsyncSession, user: Principal, credit_id: uuid.UUID
) -> MasteryCredit:
    row = await load_credit(session, user, credit_id)
    row.status = "approved"
    row.approved_by = user.id
    await session.flush()
    await session.refresh(row)
    return row


async def redeem_credit(
    session: AsyncSession, user: Principal, credit_id: uuid.UUID, *, redeemed_for: str
) -> MasteryCredit:
    row = await load_credit(session, user, credit_id)
    if row.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only approved credits can be redeemed",
        )
    row.status = "redeemed"
    row.redeemed_for = redeemed_for
    await session.flush()
    await session.refresh(row)
    return row


# ── Faculty analytics ────────────────────────────────────────────────────────


async def course_analytics(
    session: AsyncSession, user: Principal, course_id: uuid.UUID
) -> dict:
    await _load_course(session, user, course_id)

    # Enrollments pinned to any version of this course.
    enrollment_ids = (
        (
            await session.execute(
                select(Enrollment.id)
                .join(CourseVersion, CourseVersion.id == Enrollment.course_version_id)
                .where(CourseVersion.course_id == course_id)
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    enrollment_ids = list(enrollment_ids)

    readiness_states: dict[str, int] = {}
    submissions_by_status: dict[str, int] = {}
    publication_candidates = 0
    credit_totals = {"recommended": 0.0, "approved": 0.0, "redeemed": 0.0}
    evaluations: dict = {"finalized": 0, "pending": 0, "average_grade": None}

    if enrollment_ids:
        rs_rows = (
            await session.execute(
                select(NodeProgress.readiness_state, func.count())
                .where(
                    NodeProgress.enrollment_id.in_(enrollment_ids),
                    NodeProgress.readiness_state.is_not(None),
                )
                .group_by(NodeProgress.readiness_state)
            )
        ).all()
        readiness_states = {state: count for state, count in rs_rows}

        sub_rows = (
            await session.execute(
                select(AssessmentSubmission.status, func.count())
                .where(AssessmentSubmission.enrollment_id.in_(enrollment_ids))
                .group_by(AssessmentSubmission.status)
            )
        ).all()
        submissions_by_status = {st: count for st, count in sub_rows}

        publication_candidates = (
            await session.execute(
                select(func.count())
                .select_from(ContributionVersion)
                .where(
                    ContributionVersion.enrollment_id.in_(enrollment_ids),
                    ContributionVersion.verification_status.in_(("pending", "verified")),
                )
            )
        ).scalar_one()

        credit_rows = (
            await session.execute(
                select(MasteryCredit.status, func.sum(MasteryCredit.amount))
                .where(MasteryCredit.enrollment_id.in_(enrollment_ids))
                .group_by(MasteryCredit.status)
            )
        ).all()
        for st, total in credit_rows:
            if st in credit_totals:
                credit_totals[st] = float(total or 0)

        eval_rows = (
            await session.execute(
                select(
                    AssessmentEvaluation.finalized,
                    func.count(),
                    func.avg(AssessmentEvaluation.grade),
                )
                .join(
                    AssessmentSubmission,
                    AssessmentSubmission.id == AssessmentEvaluation.submission_id,
                )
                .where(AssessmentSubmission.enrollment_id.in_(enrollment_ids))
                .group_by(AssessmentEvaluation.finalized)
            )
        ).all()
        avg_grades: list[float] = []
        for finalized, count, avg in eval_rows:
            if finalized:
                evaluations["finalized"] = count
                if avg is not None:
                    avg_grades.append(float(avg))
            else:
                evaluations["pending"] = count
        if avg_grades:
            evaluations["average_grade"] = round(sum(avg_grades) / len(avg_grades), 2)

    # Surface the approved analytics design artifact (continuous-improvement).
    analytics_artifact = (
        await session.execute(
            select(CourseDesignArtifact)
            .where(
                CourseDesignArtifact.course_id == course_id,
                CourseDesignArtifact.stage_key == "analytics",
            )
            .order_by(CourseDesignArtifact.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return {
        "course_id": course_id,
        "readiness_states": readiness_states,
        "submissions_by_status": submissions_by_status,
        "evaluations": evaluations,
        "publication_candidates": int(publication_candidates),
        "mastery_credits": credit_totals,
        "continuous_improvement": (
            analytics_artifact.artifact if analytics_artifact else None
        ),
    }
