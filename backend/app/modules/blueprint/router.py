"""Maestro Blueprint runtime HTTP surface (learner + faculty workflows).

Mounted under ``/api/v1/blueprint``. Routes are thin: authorize, delegate to the
service, then commit. Permission model (reusing the seeded RBAC matrix):

  * Learner actions (context profile, node evidence, submission, contribution
    preparation, credit redemption)         -> ``node.progress`` + own enrollment
  * Faculty grading/evaluation/context review -> ``project.grade``
  * SME verification + credit approval/award  -> ``stage.review``
  * Assessment blueprint list/edit/approve    -> ``course.manage``
  * Analytics + publication candidates        -> ``report.view_class``
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.audit import record_audit
from app.core.deps import Principal, SessionDep, require_permission
from app.modules.blueprint import service
from app.modules.blueprint.schemas import (
    ContextProfileOut,
    ContextProfileReview,
    ContextProfileSubmit,
    ContributionAssessmentOut,
    ContributionAssessmentUpdate,
    ContributionCreate,
    ContributionOut,
    ContributionUpdate,
    ContributionVerify,
    CourseAnalyticsOut,
    CreditCreate,
    CreditOut,
    CreditRedeem,
    EvaluationCreate,
    EvaluationOut,
    FinalizeGrade,
    NodeEvidenceOut,
    NodeEvidenceResult,
    NodeEvidenceSubmit,
    ReadinessGateResult,
    RequestRevision,
    SubmissionCreate,
    SubmissionOut,
    SubmissionUpdate,
)

router = APIRouter(prefix="/blueprint", tags=["blueprint"])

CourseManager = Annotated[Principal, Depends(require_permission("course.manage"))]
Learner = Annotated[Principal, Depends(require_permission("node.progress"))]
Faculty = Annotated[Principal, Depends(require_permission("project.grade"))]
SME = Annotated[Principal, Depends(require_permission("stage.review"))]
ReportViewer = Annotated[Principal, Depends(require_permission("report.view_class"))]


# ── Contribution assessments (design / SME) ───────────────────────────────────


@router.get(
    "/courses/{course_id}/assessments",
    response_model=list[ContributionAssessmentOut],
    summary="List a course's contribution-assessment blueprints",
)
async def list_assessments(
    course_id: uuid.UUID, session: SessionDep, user: CourseManager
) -> list[ContributionAssessmentOut]:
    rows = await service.list_assessments(session, user, course_id)
    return [ContributionAssessmentOut.model_validate(r) for r in rows]


@router.get(
    "/assessments/{assessment_id}",
    response_model=ContributionAssessmentOut,
    summary="Get a contribution-assessment blueprint",
)
async def get_assessment(
    assessment_id: uuid.UUID, session: SessionDep, user: CourseManager
) -> ContributionAssessmentOut:
    row = await service.load_assessment(session, user, assessment_id)
    return ContributionAssessmentOut.model_validate(row)


@router.patch(
    "/assessments/{assessment_id}",
    response_model=ContributionAssessmentOut,
    summary="Edit a contribution-assessment blueprint",
)
async def update_assessment(
    assessment_id: uuid.UUID,
    payload: ContributionAssessmentUpdate,
    session: SessionDep,
    user: CourseManager,
) -> ContributionAssessmentOut:
    row = await service.update_assessment(
        session, user, assessment_id, payload.model_dump(exclude_unset=True)
    )
    await record_audit(
        session, tenant_id=row.tenant_id, actor_id=user.id,
        action="blueprint.assessment.update", object_type="contribution_assessment",
        object_id=row.id,
    )
    await session.commit()
    return ContributionAssessmentOut.model_validate(row)


@router.post(
    "/assessments/{assessment_id}/approve",
    response_model=ContributionAssessmentOut,
    summary="Approve a contribution-assessment blueprint",
)
async def approve_assessment(
    assessment_id: uuid.UUID, session: SessionDep, user: CourseManager
) -> ContributionAssessmentOut:
    row = await service.approve_assessment(session, user, assessment_id)
    await session.commit()
    return ContributionAssessmentOut.model_validate(row)


# ── Context profile ────────────────────────────────────────────────────────────


@router.post(
    "/assessments/{assessment_id}/context-profile",
    response_model=ContextProfileOut,
    summary="Submit a personalized assessment context profile (learner)",
)
async def submit_context_profile(
    assessment_id: uuid.UUID,
    payload: ContextProfileSubmit,
    session: SessionDep,
    user: Learner,
) -> ContextProfileOut:
    row = await service.submit_context_profile(
        session, user, assessment_id,
        enrollment_id=payload.enrollment_id, profile=payload.profile,
    )
    await session.commit()
    return ContextProfileOut.model_validate(row)


@router.post(
    "/context-profiles/{profile_id}/review",
    response_model=ContextProfileOut,
    summary="Approve/reject a context profile (faculty)",
)
async def review_context_profile(
    profile_id: uuid.UUID,
    payload: ContextProfileReview,
    session: SessionDep,
    user: Faculty,
) -> ContextProfileOut:
    row = await service.review_context_profile(
        session, user, profile_id, approve=payload.approve, note=payload.note
    )
    await session.commit()
    return ContextProfileOut.model_validate(row)


# ── Node evidence + readiness ─────────────────────────────────────────────────


@router.post(
    "/enrollments/{enrollment_id}/nodes/{node_id}/evidence",
    response_model=NodeEvidenceResult,
    summary="Submit node evidence and receive a readiness state (learner)",
)
async def submit_node_evidence(
    enrollment_id: uuid.UUID,
    node_id: uuid.UUID,
    payload: NodeEvidenceSubmit,
    session: SessionDep,
    user: Learner,
) -> NodeEvidenceResult:
    row = await service.submit_node_evidence(
        session, user, enrollment_id, node_id,
        evidence=payload.evidence, readiness_state=payload.readiness_state,
    )
    await session.commit()
    return NodeEvidenceResult(
        evidence=NodeEvidenceOut.model_validate(row),
        readiness_state=row.readiness_state,
        ai_companion_message=row.ai_companion_message,
    )


@router.get(
    "/enrollments/{enrollment_id}/nodes/{node_id}/evidence",
    response_model=list[NodeEvidenceOut],
    summary="List a learner's node evidence log",
)
async def list_node_evidence(
    enrollment_id: uuid.UUID,
    node_id: uuid.UUID,
    session: SessionDep,
    user: Learner,
) -> list[NodeEvidenceOut]:
    rows = await service.list_node_evidence(session, user, enrollment_id, node_id)
    return [NodeEvidenceOut.model_validate(r) for r in rows]


@router.get(
    "/assessments/{assessment_id}/readiness",
    response_model=ReadinessGateResult,
    summary="Check assessment readiness gate for an enrollment (learner)",
)
async def check_readiness(
    assessment_id: uuid.UUID,
    session: SessionDep,
    user: Learner,
    enrollment_id: Annotated[uuid.UUID, Query()] = ...,
) -> ReadinessGateResult:
    data = await service.check_readiness(session, user, assessment_id, enrollment_id)
    return ReadinessGateResult(**data)


# ── Submissions ────────────────────────────────────────────────────────────────


@router.post(
    "/assessments/{assessment_id}/submissions",
    response_model=SubmissionOut,
    summary="Create/submit a formal assessment package (learner)",
)
async def create_submission(
    assessment_id: uuid.UUID,
    payload: SubmissionCreate,
    session: SessionDep,
    user: Learner,
) -> SubmissionOut:
    row = await service.create_submission(
        session, user, assessment_id,
        enrollment_id=payload.enrollment_id, package=payload.package, submit=payload.submit,
    )
    await record_audit(
        session, tenant_id=row.tenant_id, actor_id=user.id,
        action="blueprint.submission.create", object_type="assessment_submission",
        object_id=row.id, metadata={"status": row.status},
    )
    await session.commit()
    return SubmissionOut.model_validate(row)


@router.get(
    "/submissions/{submission_id}",
    response_model=SubmissionOut,
    summary="Get a submission",
)
async def get_submission(
    submission_id: uuid.UUID, session: SessionDep, user: Learner
) -> SubmissionOut:
    row = await service.load_submission(session, user, submission_id)
    return SubmissionOut.model_validate(row)


@router.patch(
    "/submissions/{submission_id}",
    response_model=SubmissionOut,
    summary="Edit a draft/revision submission (learner)",
)
async def update_submission(
    submission_id: uuid.UUID,
    payload: SubmissionUpdate,
    session: SessionDep,
    user: Learner,
) -> SubmissionOut:
    row = await service.update_submission(
        session, user, submission_id, package=payload.package
    )
    await session.commit()
    return SubmissionOut.model_validate(row)


@router.post(
    "/submissions/{submission_id}/submit",
    response_model=SubmissionOut,
    summary="Finalize a draft submission (learner)",
)
async def submit_submission(
    submission_id: uuid.UUID, session: SessionDep, user: Learner
) -> SubmissionOut:
    row = await service.submit_submission(session, user, submission_id)
    await session.commit()
    return SubmissionOut.model_validate(row)


@router.get(
    "/submissions",
    response_model=list[SubmissionOut],
    summary="List submissions (by assessment and/or enrollment)",
)
async def list_submissions(
    session: SessionDep,
    user: Learner,
    assessment_id: Annotated[uuid.UUID | None, Query()] = None,
    enrollment_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[SubmissionOut]:
    rows = await service.list_submissions(
        session, user, assessment_id=assessment_id, enrollment_id=enrollment_id
    )
    return [SubmissionOut.model_validate(r) for r in rows]


# ── Evaluation / grading (faculty) ───────────────────────────────────────────


@router.post(
    "/submissions/{submission_id}/evaluate",
    response_model=EvaluationOut,
    summary="Record a rubric-based evaluation recommendation (faculty)",
)
async def evaluate_submission(
    submission_id: uuid.UUID,
    payload: EvaluationCreate,
    session: SessionDep,
    user: Faculty,
) -> EvaluationOut:
    row = await service.evaluate_submission(
        session, user, submission_id, data=payload.model_dump()
    )
    await record_audit(
        session, tenant_id=row.tenant_id, actor_id=user.id,
        action="blueprint.submission.evaluate", object_type="assessment_evaluation",
        object_id=row.id,
    )
    await session.commit()
    return EvaluationOut.model_validate(row)


@router.post(
    "/submissions/{submission_id}/finalize-grade",
    response_model=EvaluationOut,
    summary="Finalize the academic grade for a submission (faculty)",
)
async def finalize_grade(
    submission_id: uuid.UUID,
    payload: FinalizeGrade,
    session: SessionDep,
    user: Faculty,
) -> EvaluationOut:
    row = await service.finalize_grade(
        session, user, submission_id,
        grade=payload.grade, feedback_learner=payload.feedback_learner,
        publication_potential=payload.publication_potential,
    )
    await record_audit(
        session, tenant_id=row.tenant_id, actor_id=user.id,
        action="blueprint.submission.grade", object_type="assessment_evaluation",
        object_id=row.id, metadata={"grade": payload.grade},
    )
    await session.commit()
    return EvaluationOut.model_validate(row)


@router.post(
    "/submissions/{submission_id}/request-revision",
    response_model=SubmissionOut,
    summary="Request a revision before final grading (faculty)",
)
async def request_revision(
    submission_id: uuid.UUID,
    payload: RequestRevision,
    session: SessionDep,
    user: Faculty,
) -> SubmissionOut:
    row = await service.request_revision(
        session, user, submission_id, kind=payload.kind, note=payload.note
    )
    await session.commit()
    return SubmissionOut.model_validate(row)


@router.get(
    "/submissions/{submission_id}/evaluation",
    response_model=EvaluationOut | None,
    summary="Get the latest evaluation for a submission",
)
async def get_evaluation(
    submission_id: uuid.UUID, session: SessionDep, user: Learner
) -> EvaluationOut | None:
    row = await service.get_evaluation(session, user, submission_id)
    return EvaluationOut.model_validate(row) if row else None


# ── Contribution versions ────────────────────────────────────────────────────


@router.post(
    "/submissions/{submission_id}/contribution",
    response_model=ContributionOut,
    summary="Prepare a contribution version from a submission (learner)",
)
async def prepare_contribution(
    submission_id: uuid.UUID,
    payload: ContributionCreate,
    session: SessionDep,
    user: Learner,
) -> ContributionOut:
    row = await service.prepare_contribution(
        session, user, submission_id, data=payload.model_dump()
    )
    await session.commit()
    return ContributionOut.model_validate(row)


@router.patch(
    "/contributions/{contribution_id}",
    response_model=ContributionOut,
    summary="Edit a contribution version (learner)",
)
async def update_contribution(
    contribution_id: uuid.UUID,
    payload: ContributionUpdate,
    session: SessionDep,
    user: Learner,
) -> ContributionOut:
    row = await service.update_contribution(
        session, user, contribution_id, data=payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return ContributionOut.model_validate(row)


@router.post(
    "/contributions/{contribution_id}/verify",
    response_model=ContributionOut,
    summary="SME verification of a contribution (visibility + status)",
)
async def verify_contribution(
    contribution_id: uuid.UUID,
    payload: ContributionVerify,
    session: SessionDep,
    user: SME,
) -> ContributionOut:
    row = await service.verify_contribution(
        session, user, contribution_id,
        verification_status=payload.verification_status,
        visibility_level=payload.visibility_level, note=payload.note,
    )
    await record_audit(
        session, tenant_id=row.tenant_id, actor_id=user.id,
        action="blueprint.contribution.verify", object_type="contribution_version",
        object_id=row.id, metadata={"verification_status": payload.verification_status},
    )
    await session.commit()
    return ContributionOut.model_validate(row)


@router.get(
    "/enrollments/{enrollment_id}/contributions",
    response_model=list[ContributionOut],
    summary="List an enrollment's contribution versions",
)
async def list_enrollment_contributions(
    enrollment_id: uuid.UUID, session: SessionDep, user: Learner
) -> list[ContributionOut]:
    rows = await service.list_contributions_for_enrollment(session, user, enrollment_id)
    return [ContributionOut.model_validate(r) for r in rows]


@router.get(
    "/courses/{course_id}/contributions",
    response_model=list[ContributionOut],
    summary="List publication candidates for a course (faculty)",
)
async def list_publication_candidates(
    course_id: uuid.UUID, session: SessionDep, user: ReportViewer
) -> list[ContributionOut]:
    rows = await service.list_publication_candidates(session, user, course_id)
    return [ContributionOut.model_validate(r) for r in rows]


# ── Mastery credits ────────────────────────────────────────────────────────────


@router.get(
    "/enrollments/{enrollment_id}/credits",
    response_model=list[CreditOut],
    summary="List an enrollment's Mastery Credit ledger",
)
async def list_credits(
    enrollment_id: uuid.UUID, session: SessionDep, user: Learner
) -> list[CreditOut]:
    rows = await service.list_credits(session, user, enrollment_id)
    return [CreditOut.model_validate(r) for r in rows]


@router.post(
    "/enrollments/{enrollment_id}/credits",
    response_model=CreditOut,
    summary="Recommend/award a Mastery Credit (faculty/SME)",
)
async def award_credit(
    enrollment_id: uuid.UUID,
    payload: CreditCreate,
    session: SessionDep,
    user: Faculty,
) -> CreditOut:
    row = await service.award_credit(
        session, user, enrollment_id,
        source_type=payload.source_type, source_id=payload.source_id,
        amount=payload.amount, rationale=payload.rationale,
    )
    await session.commit()
    return CreditOut.model_validate(row)


@router.post(
    "/credits/{credit_id}/approve",
    response_model=CreditOut,
    summary="Approve a recommended Mastery Credit (SME)",
)
async def approve_credit(
    credit_id: uuid.UUID, session: SessionDep, user: SME
) -> CreditOut:
    row = await service.approve_credit(session, user, credit_id)
    await session.commit()
    return CreditOut.model_validate(row)


@router.post(
    "/credits/{credit_id}/redeem",
    response_model=CreditOut,
    summary="Redeem an approved Mastery Credit (faculty)",
)
async def redeem_credit(
    credit_id: uuid.UUID,
    payload: CreditRedeem,
    session: SessionDep,
    user: Faculty,
) -> CreditOut:
    row = await service.redeem_credit(
        session, user, credit_id, redeemed_for=payload.redeemed_for
    )
    await session.commit()
    return CreditOut.model_validate(row)


# ── Faculty analytics ────────────────────────────────────────────────────────


@router.get(
    "/courses/{course_id}/analytics",
    response_model=CourseAnalyticsOut,
    summary="Faculty dashboard + continuous-improvement analytics",
)
async def course_analytics(
    course_id: uuid.UUID, session: SessionDep, user: ReportViewer
) -> CourseAnalyticsOut:
    data = await service.course_analytics(session, user, course_id)
    return CourseAnalyticsOut(**data)


__all__ = ["router"]
