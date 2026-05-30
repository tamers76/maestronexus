"""Maestro Blueprint domain models (docs: Maestro Blueprint.docx).

These tables add *approved, queryable* domain state on top of the ``StageRun``
execution/audit log:

Design-time (promoted on SME approval of a stage run):
  * ``CourseDesignArtifact``  — current approved artifact snapshot per stage.
  * ``CourseSubtopic``        — self-paced learning territories (Stage 6).
  * ``ContributionAssessment``— formal assessment blueprints (Stages 3-5,11-15).
  * ``LearningEffortMap``     — learning-hour / accreditation equivalency (St17).

Runtime (created during the learner / faculty journey):
  * ``NodeEvidence``          — learner evidence + readiness state per node.
  * ``AssessmentContextProfile`` — personalized assessment context (Stage 3/5).
  * ``AssessmentSubmission``  — formal submission package (Stage 12).
  * ``AssessmentEvaluation``  — rubric evaluation + grade finalization (St12-13).
  * ``ContributionVersion``   — public/internal contribution + verification (14-15).
  * ``MasteryCredit``         — optional opportunity-currency ledger (Stage 16).

All tables reference other modules by table name (string FKs) so the Blueprint
module never imports another module's model classes.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    Base,
    CreatedByMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPKMixin,
)

# ── Design-time approved artifacts ────────────────────────────────────────────


class CourseDesignArtifact(UUIDPKMixin, TenantMixin, TimestampMixin, CreatedByMixin, Base):
    """The current approved design artifact for one stage on a course.

    Upserted on SME approval of a ``StageRun`` (idempotent re-promotion). Keeps
    ``StageRun`` history intact while exposing a single queryable approved state.
    """

    __tablename__ = "course_design_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "course_id", "course_version_id", "stage_key", name="uq_design_artifact"
        ),
        Index("ix_design_artifact_course_stage", "course_id", "stage_key"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    course_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    stage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stage_runs.id", ondelete="SET NULL"), nullable=True
    )
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    artifact: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class CourseSubtopic(UUIDPKMixin, TenantMixin, TimestampMixin, CreatedByMixin, Base):
    """A self-paced learning territory under a refined CLO (Blueprint Stage 6)."""

    __tablename__ = "course_subtopics"
    __table_args__ = (
        UniqueConstraint("course_id", "subtopic_key", name="uq_course_subtopic_key"),
        Index("ix_course_subtopic_course", "course_id"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    course_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    outcome_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_outcomes.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Stable identifier from the stage artifact (for idempotent re-promotion).
    subtopic_key: Mapped[str] = mapped_column(String(128), nullable=False)
    clo_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_function: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stage_runs.id", ondelete="SET NULL"), nullable=True
    )


class ContributionAssessment(UUIDPKMixin, TenantMixin, TimestampMixin, CreatedByMixin, Base):
    """A formal contribution-assessment blueprint (distinct from node quizzes).

    Assembled/updated by the assessment-redesign, weighting/rubric, integrity,
    and readiness-gate stages. ``status`` flips to ``approved`` on promotion.
    """

    __tablename__ = "contribution_assessments"
    __table_args__ = (
        UniqueConstraint("course_id", "assessment_key", name="uq_contribution_assessment_key"),
        Index("ix_contribution_assessment_course", "course_id"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    course_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Stable identifier from the stage artifact (for idempotent re-promotion).
    assessment_key: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    contribution_purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    clo_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    fixed_core: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    personalized_variables: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    required_artifact: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_formats: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Rubric criteria + per-criterion weights.
    rubric: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    integrity_requirements: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    context_profile_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    readiness_gate: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    publication_potential: Mapped[str | None] = mapped_column(String(32), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stage_runs.id", ondelete="SET NULL"), nullable=True
    )


class LearningEffortMap(UUIDPKMixin, TenantMixin, TimestampMixin, CreatedByMixin, Base):
    """Learning-effort / credit-hour equivalency map (Blueprint Stage 17)."""

    __tablename__ = "learning_effort_maps"
    __table_args__ = (
        UniqueConstraint("course_id", "course_version_id", name="uq_effort_map_course_version"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    course_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    total_estimated_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    accreditation_alignment: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stage_runs.id", ondelete="SET NULL"), nullable=True
    )


# ── Learner runtime ───────────────────────────────────────────────────────────


class NodeEvidence(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """A learner's evidence submission for a node + interpreted readiness state.

    Distinct from ``NodeProgress`` (the state machine): this is the evidence log
    that drives readiness states (not_ready / partially_ready / ready / advanced)
    and the AI Companion's feedback (Blueprint Stage 8).
    """

    __tablename__ = "node_evidence"
    __table_args__ = (Index("ix_node_evidence_enrollment_node", "enrollment_id", "node_id"),)

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False
    )
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # not_ready | partially_ready | ready | advanced
    readiness_state: Mapped[str] = mapped_column(String(32), nullable=False, default="not_ready")
    feedback: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ai_companion_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssessmentContextProfile(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """A learner's personalized assessment context profile (Blueprint Stage 3/5)."""

    __tablename__ = "assessment_context_profiles"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id", "enrollment_id", name="uq_context_profile_assessment_enrollment"
        ),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contribution_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # submitted | approved | rejected
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssessmentSubmission(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """A learner's formal contribution-assessment submission package (Stage 12)."""

    __tablename__ = "assessment_submissions"
    __table_args__ = (
        Index("ix_assessment_submission_enrollment", "enrollment_id"),
        Index("ix_assessment_submission_assessment", "assessment_id"),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contribution_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )
    context_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_context_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Package: artifact, decision_log, ai_use_disclosure, process_checkpoints,
    # reflection, references, evidence_appendix, defense.
    package: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # draft | submitted | under_review | revision_requested | graded
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssessmentEvaluation(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Rubric-based evaluation + grade finalization for a submission (St12-13)."""

    __tablename__ = "assessment_evaluations"
    __table_args__ = (Index("ix_assessment_evaluation_submission", "submission_id"),)

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Per-criterion rubric scores + overall recommendation.
    rubric_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # accept | minor_revision | major_revision | missing_process_evidence |
    # ai_use_clarification | defense_requested | sme_review | not_recommended
    recommendation: Mapped[str | None] = mapped_column(String(48), nullable=True)
    feedback_learner: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_sme: Mapped[str | None] = mapped_column(Text, nullable=True)
    integrity_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    publication_potential: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grade: Mapped[float | None] = mapped_column(Float, nullable=True)
    finalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # ai | sme
    evaluator_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="ai")
    evaluated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ContributionVersion(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """A public/internal contribution version + verification (Blueprint St14-15)."""

    __tablename__ = "contribution_versions"
    __table_args__ = (Index("ix_contribution_version_enrollment", "enrollment_id"),)

    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )
    format: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    contribution_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    anonymized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # private | internal | public
    visibility_level: Mapped[str] = mapped_column(String(32), nullable=False, default="private")
    # pending | verified | needs_revision | rejected
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    license: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class MasteryCredit(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """An optional Mastery / Excellence Credit ledger entry (Blueprint Stage 16)."""

    __tablename__ = "mastery_credits"
    __table_args__ = (Index("ix_mastery_credit_enrollment", "enrollment_id"),)

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )
    # node | assessment | contribution | other
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="node")
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    # recommended | approved | redeemed | rejected
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="recommended")
    redeemed_for: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


__all__ = [
    "CourseDesignArtifact",
    "CourseSubtopic",
    "ContributionAssessment",
    "LearningEffortMap",
    "NodeEvidence",
    "AssessmentContextProfile",
    "AssessmentSubmission",
    "AssessmentEvaluation",
    "ContributionVersion",
    "MasteryCredit",
]
