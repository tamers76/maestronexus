"""stages and ai settings

Adds the ``stage_runs`` table (StageRun: one execution of a stage feature on a
course) and the ``ai_settings`` table (per-tenant runtime AI/council/stage config).

Revision ID: a1b2c3d4e5f6
Revises: 90083b9bbe3f
Create Date: 2026-05-30 16:20:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "90083b9bbe3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_settings",
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_ai_settings_tenant"),
    )
    op.create_index(op.f("ix_ai_settings_tenant_id"), "ai_settings", ["tenant_id"], unique=False)

    op.create_table(
        "stage_runs",
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("course_version_id", sa.UUID(), nullable=True),
        sa.Column("stage_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("execution_mode", sa.String(length=32), nullable=False),
        sa.Column("input_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "council_transcript", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["course_version_id"], ["course_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stage_runs_tenant_id"), "stage_runs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_stage_runs_course_id"), "stage_runs", ["course_id"], unique=False)
    op.create_index(op.f("ix_stage_runs_stage_key"), "stage_runs", ["stage_key"], unique=False)
    op.create_index(
        "ix_stage_runs_course_stage", "stage_runs", ["course_id", "stage_key"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_stage_runs_course_stage", table_name="stage_runs")
    op.drop_index(op.f("ix_stage_runs_stage_key"), table_name="stage_runs")
    op.drop_index(op.f("ix_stage_runs_course_id"), table_name="stage_runs")
    op.drop_index(op.f("ix_stage_runs_tenant_id"), table_name="stage_runs")
    op.drop_table("stage_runs")
    op.drop_index(op.f("ix_ai_settings_tenant_id"), table_name="ai_settings")
    op.drop_table("ai_settings")
