"""Maestro Blueprint runtime request/response schemas.

Contract handed to the frontend agent. Readiness states follow the Blueprint:
``not_ready`` | ``partially_ready`` | ``ready`` | ``advanced``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ReadinessState = Literal["not_ready", "partially_ready", "ready", "advanced"]
GateOutcome = Literal[
    "ready_to_submit", "ready_with_caution", "needs_targeted_support", "not_ready"
]
SubmissionStatus = Literal[
    "draft", "submitted", "under_review", "revision_requested", "graded"
]
EvaluationRecommendation = Literal[
    "accept",
    "minor_revision",
    "major_revision",
    "missing_process_evidence",
    "ai_use_clarification",
    "defense_requested",
    "sme_review",
    "not_recommended",
]
VisibilityLevel = Literal["private", "internal", "public"]
VerificationStatus = Literal["pending", "verified", "needs_revision", "rejected"]
CreditStatus = Literal["recommended", "approved", "redeemed", "rejected"]


# ── Contribution assessments (design / SME) ───────────────────────────────────


class ContributionAssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    course_version_id: uuid.UUID | None
    assessment_key: str
    title: str
    original_title: str | None
    contribution_purpose: str | None
    clo_codes: list
    fixed_core: dict
    personalized_variables: list
    required_artifact: str | None
    output_formats: list
    rubric: dict
    weight: float | None
    integrity_requirements: dict
    context_profile_schema: dict
    readiness_gate: dict
    publication_potential: str | None
    position: int
    status: str
    created_at: datetime
    updated_at: datetime


class ContributionAssessmentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    contribution_purpose: str | None = None
    clo_codes: list | None = None
    fixed_core: dict | None = None
    personalized_variables: list | None = None
    required_artifact: str | None = None
    output_formats: list | None = None
    rubric: dict | None = None
    weight: float | None = None
    integrity_requirements: dict | None = None
    context_profile_schema: dict | None = None
    readiness_gate: dict | None = None
    publication_potential: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=32)


# ── Context profile ────────────────────────────────────────────────────────────


class ContextProfileSubmit(BaseModel):
    enrollment_id: uuid.UUID
    profile: dict = Field(default_factory=dict)


class ContextProfileReview(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


class ContextProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    enrollment_id: uuid.UUID
    profile: dict
    status: str
    reviewed_by: uuid.UUID | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime


# ── Node evidence + readiness ─────────────────────────────────────────────────


class NodeEvidenceSubmit(BaseModel):
    evidence: dict = Field(default_factory=dict)
    # Optional learner/AI self-assessed readiness; server may recompute.
    readiness_state: ReadinessState | None = None


class NodeEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    enrollment_id: uuid.UUID
    node_id: uuid.UUID
    evidence: dict
    readiness_state: str
    feedback: dict
    ai_companion_message: str | None
    created_at: datetime


class NodeEvidenceResult(BaseModel):
    evidence: NodeEvidenceOut
    readiness_state: str
    ai_companion_message: str | None = None


# ── Readiness gate ─────────────────────────────────────────────────────────────


class GateCheck(BaseModel):
    check: str
    passed: bool
    detail: str | None = None


class ReadinessGateResult(BaseModel):
    assessment_id: uuid.UUID
    enrollment_id: uuid.UUID
    outcome: GateOutcome
    checks: list[GateCheck]
    missing_node_keys: list[str] = Field(default_factory=list)
    context_profile_approved: bool = False


# ── Submissions ────────────────────────────────────────────────────────────────


class SubmissionCreate(BaseModel):
    enrollment_id: uuid.UUID
    package: dict = Field(default_factory=dict)
    # When true the submission is finalized (status=submitted) immediately.
    submit: bool = False


class SubmissionUpdate(BaseModel):
    package: dict | None = None


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    enrollment_id: uuid.UUID
    context_profile_id: uuid.UUID | None
    package: dict
    version: int
    status: str
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ── Evaluations / grading ───────────────────────────────────────────────────────


class EvaluationCreate(BaseModel):
    rubric_scores: dict = Field(default_factory=dict)
    recommendation: EvaluationRecommendation | None = None
    feedback_learner: str | None = None
    feedback_sme: str | None = None
    integrity_flag: bool = False
    publication_potential: str | None = Field(default=None, max_length=32)
    grade: float | None = None
    evaluator_kind: Literal["ai", "sme"] = "ai"


class FinalizeGrade(BaseModel):
    grade: float
    feedback_learner: str | None = None
    publication_potential: str | None = Field(default=None, max_length=32)


class RequestRevision(BaseModel):
    kind: Literal["minor", "major"] = "minor"
    note: str | None = Field(default=None, max_length=2000)


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID
    rubric_scores: dict
    recommendation: str | None
    feedback_learner: str | None
    feedback_sme: str | None
    integrity_flag: bool
    publication_potential: str | None
    grade: float | None
    finalized: bool
    evaluator_kind: str
    evaluated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ── Contribution versions ────────────────────────────────────────────────────


class ContributionCreate(BaseModel):
    format: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=512)
    summary: str | None = None
    body: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    consent: bool = False
    anonymized: bool = False
    visibility_level: VisibilityLevel = "private"
    license: str | None = Field(default=None, max_length=255)


class ContributionUpdate(BaseModel):
    format: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=512)
    summary: str | None = None
    body: dict | None = None
    metadata: dict | None = None
    consent: bool | None = None
    anonymized: bool | None = None
    visibility_level: VisibilityLevel | None = None
    license: str | None = Field(default=None, max_length=255)


class ContributionVerify(BaseModel):
    verification_status: VerificationStatus
    visibility_level: VisibilityLevel | None = None
    note: str | None = Field(default=None, max_length=2000)


class ContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID | None
    enrollment_id: uuid.UUID
    format: str | None
    title: str | None
    summary: str | None
    body: dict
    metadata: dict = Field(validation_alias="contribution_metadata")
    consent: bool
    anonymized: bool
    visibility_level: str
    verification_status: str
    license: str | None
    verified_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ── Mastery credits ────────────────────────────────────────────────────────────


class CreditCreate(BaseModel):
    source_type: Literal["node", "assessment", "contribution", "other"] = "node"
    source_id: uuid.UUID | None = None
    amount: float = Field(ge=0)
    rationale: str | None = None


class CreditRedeem(BaseModel):
    redeemed_for: str = Field(min_length=1, max_length=255)


class CreditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    enrollment_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID | None
    amount: float
    rationale: str | None
    status: str
    redeemed_for: str | None
    approved_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ── Faculty analytics ────────────────────────────────────────────────────────


class CourseAnalyticsOut(BaseModel):
    course_id: uuid.UUID
    readiness_states: dict[str, int]
    submissions_by_status: dict[str, int]
    evaluations: dict[str, Any]
    publication_candidates: int
    mastery_credits: dict[str, Any]
    continuous_improvement: dict | None = None


__all__ = [
    "ReadinessState",
    "ContributionAssessmentOut",
    "ContributionAssessmentUpdate",
    "ContextProfileSubmit",
    "ContextProfileReview",
    "ContextProfileOut",
    "NodeEvidenceSubmit",
    "NodeEvidenceOut",
    "NodeEvidenceResult",
    "GateCheck",
    "ReadinessGateResult",
    "SubmissionCreate",
    "SubmissionUpdate",
    "SubmissionOut",
    "EvaluationCreate",
    "FinalizeGrade",
    "RequestRevision",
    "EvaluationOut",
    "ContributionCreate",
    "ContributionUpdate",
    "ContributionVerify",
    "ContributionOut",
    "CreditCreate",
    "CreditRedeem",
    "CreditOut",
    "CourseAnalyticsOut",
]
