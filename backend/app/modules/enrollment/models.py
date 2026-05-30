"""Enrollment & progress models (docs/05, docs/12).

Per-learner *state* lives here, kept separate from the shared, immutable course
graph (owned by the ``courses`` module). An enrollment pins a learner to a
specific ``course_version`` so the graph they progress through never shifts.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPKMixin,
)


class Class(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """A teacher-owned cohort of learners."""

    __tablename__ = "classes"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class Enrollment(UUIDPKMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "class_id", name="uq_enrollment_user_class"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class NodeProgress(UUIDPKMixin, TimestampMixin, Base):
    """A learner's state on a single node (locked → available → completed → mastered)."""

    __tablename__ = "node_progress"
    __table_args__ = (
        UniqueConstraint("enrollment_id", "node_id", name="uq_node_progress"),
        Index("ix_node_progress_enrollment_state", "enrollment_id", "state"),
    )

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enrollments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="locked")
    # Blueprint readiness state derived from node evidence (independent of the
    # locked/available/completed/mastered traversal state). One of:
    # not_ready | partially_ready | ready | advanced (or None before evidence).
    readiness_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MasteryRecord(UUIDPKMixin, TimestampMixin, Base):
    """Evidence backing ``mastery_gate`` evaluation (docs/04, docs/12)."""

    __tablename__ = "mastery_records"

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enrollments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=True
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="SET NULL"), nullable=True
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


__all__ = ["Class", "Enrollment", "NodeProgress", "MasteryRecord"]
