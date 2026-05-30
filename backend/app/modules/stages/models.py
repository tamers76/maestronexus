"""Stage run model: one execution of a stage feature against a course.

A ``StageRun`` is the persisted record of running a stage (single or council).
The latest ``succeeded`` run per ``(course_id, stage_key)`` is treated as that
stage's *current artifact*. Runs are tenant-scoped and audited; high-risk or
flagged runs route to an SME via ``review_status`` (docx §10 governance).
"""

import uuid

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    Base,
    CreatedByMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPKMixin,
)


class StageRun(UUIDPKMixin, TenantMixin, TimestampMixin, CreatedByMixin, Base):
    __tablename__ = "stage_runs"
    __table_args__ = (
        Index("ix_stage_runs_course_stage", "course_id", "stage_key"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    stage_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # pending | running | succeeded | failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # single | council
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="single")
    # References to inputs used (upstream run ids, syllabus refs, options, model list).
    input_refs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # The produced artifact (synthesized text + any structured parse + gaps).
    output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Council member responses + chairman synthesis (empty for single runs).
    council_transcript: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # auto_ok | needs_review | approved | rejected
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="auto_ok")


__all__ = ["StageRun"]
