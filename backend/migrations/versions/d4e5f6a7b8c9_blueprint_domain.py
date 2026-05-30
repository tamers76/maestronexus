"""Maestro Blueprint domain tables + node readiness state + stage_key rename.

Adds approved design-artifact snapshots, subtopics, contribution assessments,
learning-effort maps, and the learner-runtime tables (node evidence, context
profiles, submissions, evaluations, contribution versions, Mastery Credits).
Also adds ``node_progress.readiness_state`` and migrates legacy ``stage_runs``
``stage_key`` values to the Blueprint's canonical 18-stage keys.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-30 18:40:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())

# Legacy stage_key -> canonical Blueprint stage_key.
_STAGE_RENAMES = {
    "clo_refinement": "clo_review",
    "assessment_rubrics": "assessment_weighting",
    "mastery_node_design": "mastery_nodes",
    "node_relationship_map": "node_relationships",
}


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    # ── node_progress.readiness_state ────────────────────────────────────────
    op.add_column(
        "node_progress",
        sa.Column("readiness_state", sa.String(length=32), nullable=True),
    )

    # ── Migrate legacy stage_key values to canonical keys ────────────────────
    for old, new in _STAGE_RENAMES.items():
        op.execute(
            sa.text("UPDATE stage_runs SET stage_key = :new WHERE stage_key = :old").bindparams(
                new=new, old=old
            )
        )

    # ── course_design_artifacts ──────────────────────────────────────────────
    op.create_table(
        "course_design_artifacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("course_version_id", sa.UUID(), nullable=True),
        sa.Column("stage_key", sa.String(length=64), nullable=False),
        sa.Column("source_run_id", sa.UUID(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=32),
            server_default=sa.text("'approved'"),
            nullable=False,
        ),
        sa.Column("artifact", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["course_version_id"], ["course_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["source_run_id"], ["stage_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", "course_version_id", "stage_key", name="uq_design_artifact"
        ),
    )
    op.create_index("ix_course_design_artifacts_tenant_id", "course_design_artifacts", ["tenant_id"])
    op.create_index(
        "ix_design_artifact_course_stage",
        "course_design_artifacts",
        ["course_id", "stage_key"],
    )

    # ── course_subtopics ─────────────────────────────────────────────────────
    op.create_table(
        "course_subtopics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("course_version_id", sa.UUID(), nullable=True),
        sa.Column("outcome_id", sa.UUID(), nullable=True),
        sa.Column("subtopic_key", sa.String(length=128), nullable=False),
        sa.Column("clo_code", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("learning_function", sa.String(length=64), nullable=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("attributes", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_run_id", sa.UUID(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["course_version_id"], ["course_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["outcome_id"], ["learning_outcomes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_run_id"], ["stage_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "subtopic_key", name="uq_course_subtopic_key"),
    )
    op.create_index("ix_course_subtopics_tenant_id", "course_subtopics", ["tenant_id"])
    op.create_index("ix_course_subtopic_course", "course_subtopics", ["course_id"])

    # ── contribution_assessments ─────────────────────────────────────────────
    op.create_table(
        "contribution_assessments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("course_version_id", sa.UUID(), nullable=True),
        sa.Column("assessment_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("original_title", sa.String(length=512), nullable=True),
        sa.Column("contribution_purpose", sa.Text(), nullable=True),
        sa.Column("clo_codes", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("fixed_core", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "personalized_variables",
            JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("required_artifact", sa.Text(), nullable=True),
        sa.Column("output_formats", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("rubric", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column(
            "integrity_requirements", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "context_profile_schema", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("readiness_gate", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("publication_potential", sa.String(length=32), nullable=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default=sa.text("'draft'"), nullable=False
        ),
        sa.Column("source_run_id", sa.UUID(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["course_version_id"], ["course_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["source_run_id"], ["stage_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", "assessment_key", name="uq_contribution_assessment_key"
        ),
    )
    op.create_index(
        "ix_contribution_assessments_tenant_id", "contribution_assessments", ["tenant_id"]
    )
    op.create_index(
        "ix_contribution_assessment_course", "contribution_assessments", ["course_id"]
    )

    # ── learning_effort_maps ─────────────────────────────────────────────────
    op.create_table(
        "learning_effort_maps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("course_version_id", sa.UUID(), nullable=True),
        sa.Column("total_estimated_hours", sa.Float(), nullable=True),
        sa.Column("breakdown", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("accreditation_alignment", sa.Text(), nullable=True),
        sa.Column("source_run_id", sa.UUID(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["course_version_id"], ["course_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["source_run_id"], ["stage_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", "course_version_id", name="uq_effort_map_course_version"
        ),
    )
    op.create_index("ix_learning_effort_maps_tenant_id", "learning_effort_maps", ["tenant_id"])

    # ── node_evidence ────────────────────────────────────────────────────────
    op.create_table(
        "node_evidence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("enrollment_id", sa.UUID(), nullable=False),
        sa.Column("node_id", sa.UUID(), nullable=False),
        sa.Column("evidence", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "readiness_state",
            sa.String(length=32),
            server_default=sa.text("'not_ready'"),
            nullable=False,
        ),
        sa.Column("feedback", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("ai_companion_message", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["learning_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_node_evidence_tenant_id", "node_evidence", ["tenant_id"])
    op.create_index(
        "ix_node_evidence_enrollment_node", "node_evidence", ["enrollment_id", "node_id"]
    )

    # ── assessment_context_profiles ──────────────────────────────────────────
    op.create_table(
        "assessment_context_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("enrollment_id", sa.UUID(), nullable=False),
        sa.Column("profile", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'submitted'"),
            nullable=False,
        ),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["contribution_assessments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_id", "enrollment_id", name="uq_context_profile_assessment_enrollment"
        ),
    )
    op.create_index(
        "ix_assessment_context_profiles_tenant_id", "assessment_context_profiles", ["tenant_id"]
    )

    # ── assessment_submissions ───────────────────────────────────────────────
    op.create_table(
        "assessment_submissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("enrollment_id", sa.UUID(), nullable=False),
        sa.Column("context_profile_id", sa.UUID(), nullable=True),
        sa.Column("package", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default=sa.text("'draft'"), nullable=False
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["contribution_assessments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["context_profile_id"], ["assessment_context_profiles.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assessment_submissions_tenant_id", "assessment_submissions", ["tenant_id"]
    )
    op.create_index(
        "ix_assessment_submission_enrollment", "assessment_submissions", ["enrollment_id"]
    )
    op.create_index(
        "ix_assessment_submission_assessment", "assessment_submissions", ["assessment_id"]
    )

    # ── assessment_evaluations ───────────────────────────────────────────────
    op.create_table(
        "assessment_evaluations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("submission_id", sa.UUID(), nullable=False),
        sa.Column("rubric_scores", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("recommendation", sa.String(length=48), nullable=True),
        sa.Column("feedback_learner", sa.Text(), nullable=True),
        sa.Column("feedback_sme", sa.Text(), nullable=True),
        sa.Column(
            "integrity_flag", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("publication_potential", sa.String(length=32), nullable=True),
        sa.Column("grade", sa.Float(), nullable=True),
        sa.Column("finalized", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "evaluator_kind",
            sa.String(length=16),
            server_default=sa.text("'ai'"),
            nullable=False,
        ),
        sa.Column("evaluated_by", sa.UUID(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["assessment_submissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["evaluated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assessment_evaluations_tenant_id", "assessment_evaluations", ["tenant_id"]
    )
    op.create_index(
        "ix_assessment_evaluation_submission", "assessment_evaluations", ["submission_id"]
    )

    # ── contribution_versions ────────────────────────────────────────────────
    op.create_table(
        "contribution_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("submission_id", sa.UUID(), nullable=True),
        sa.Column("enrollment_id", sa.UUID(), nullable=False),
        sa.Column("format", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("body", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("consent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("anonymized", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "visibility_level",
            sa.String(length=32),
            server_default=sa.text("'private'"),
            nullable=False,
        ),
        sa.Column(
            "verification_status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("license", sa.String(length=255), nullable=True),
        sa.Column("verified_by", sa.UUID(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["assessment_submissions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_contribution_versions_tenant_id", "contribution_versions", ["tenant_id"]
    )
    op.create_index(
        "ix_contribution_version_enrollment", "contribution_versions", ["enrollment_id"]
    )

    # ── mastery_credits ──────────────────────────────────────────────────────
    op.create_table(
        "mastery_credits",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("enrollment_id", sa.UUID(), nullable=False),
        sa.Column(
            "source_type",
            sa.String(length=32),
            server_default=sa.text("'node'"),
            nullable=False,
        ),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'recommended'"),
            nullable=False,
        ),
        sa.Column("redeemed_for", sa.String(length=255), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mastery_credits_tenant_id", "mastery_credits", ["tenant_id"])
    op.create_index("ix_mastery_credit_enrollment", "mastery_credits", ["enrollment_id"])


def downgrade() -> None:
    op.drop_table("mastery_credits")
    op.drop_table("contribution_versions")
    op.drop_table("assessment_evaluations")
    op.drop_table("assessment_submissions")
    op.drop_table("assessment_context_profiles")
    op.drop_table("node_evidence")
    op.drop_table("learning_effort_maps")
    op.drop_table("contribution_assessments")
    op.drop_table("course_subtopics")
    op.drop_table("course_design_artifacts")

    # Revert canonical stage_key values to their legacy names.
    for old, new in _STAGE_RENAMES.items():
        op.execute(
            sa.text("UPDATE stage_runs SET stage_key = :old WHERE stage_key = :new").bindparams(
                new=new, old=old
            )
        )

    op.drop_column("node_progress", "readiness_state")
