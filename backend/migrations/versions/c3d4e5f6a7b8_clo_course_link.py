"""course-linked CLOs + course intake metadata

Links ``learning_outcomes`` to a ``course`` (so extracted/refined CLOs become
first-class, course-scoped rows) and gives ``courses`` the syllabus-derived
``course_code`` / ``credit_hours`` produced by Course Intake.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-30 17:05:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Course metadata extracted from a syllabus (Course Intake / manual form).
    op.add_column("courses", sa.Column("course_code", sa.String(length=64), nullable=True))
    op.add_column("courses", sa.Column("credit_hours", sa.Integer(), nullable=True))

    # Course-linked, pedagogically-annotated CLOs.
    op.add_column(
        "learning_outcomes",
        sa.Column("course_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "learning_outcomes",
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "learning_outcomes",
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_learning_outcomes_course_id",
        "learning_outcomes",
        ["course_id"],
    )
    op.create_foreign_key(
        "fk_learning_outcomes_course_id",
        "learning_outcomes",
        "courses",
        ["course_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_learning_outcomes_course_id", "learning_outcomes", type_="foreignkey"
    )
    op.drop_index("ix_learning_outcomes_course_id", table_name="learning_outcomes")
    op.drop_column("learning_outcomes", "position")
    op.drop_column("learning_outcomes", "attributes")
    op.drop_column("learning_outcomes", "course_id")
    op.drop_column("courses", "credit_hours")
    op.drop_column("courses", "course_code")
