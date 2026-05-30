"""Project-based learning models (docs/08, docs/12).

Submissions are always *per learner* (even for collaborative projects). Teachers
grade only their own classes' submissions (object-level scope, docs/02).
"""

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedByMixin, TimestampMixin, UUIDPKMixin


class Project(UUIDPKMixin, TimestampMixin, CreatedByMixin, Base):
    __tablename__ = "projects"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    collaborative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_submissions: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ProjectSubmission(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "project_submissions"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Rubric(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "rubrics"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Grade(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "grades"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    grader_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rubric_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Feedback(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "feedback"

    grade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_type: Mapped[str] = mapped_column(String(32), nullable=False, default="teacher")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")


__all__ = ["Project", "ProjectSubmission", "Rubric", "Grade", "Feedback"]
