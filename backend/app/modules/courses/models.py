"""Course graph + skills/outcomes models (docs/04, docs/12).

The course graph (definition) is kept separate from per-learner progress (state,
owned by the ``enrollment`` module). A course is an editable container; published
artifacts live on immutable ``CourseVersion`` snapshots.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    Base,
    CreatedByMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPKMixin,
)

# ── Course graph ────────────────────────────────────────────────────────────


class Course(UUIDPKMixin, TenantMixin, TimestampMixin, CreatedByMixin, Base):
    __tablename__ = "courses"

    program_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programs.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")


class CourseVersion(UUIDPKMixin, TimestampMixin, CreatedByMixin, Base):
    """Immutable published snapshot of a course's graph."""

    __tablename__ = "course_versions"
    __table_args__ = (UniqueConstraint("course_id", "version", name="uq_course_version"),)

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningNode(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "learning_nodes"

    course_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(48), nullable=False, default="lesson")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    learning_objective: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    mastery_rule: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    completion_rule: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    estimated_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # React Flow canvas position + arbitrary node metadata.
    node_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class NodeDependency(UUIDPKMixin, Base):
    """Directed edge between nodes (e.g. requires, mastery_gate)."""

    __tablename__ = "node_dependencies"
    __table_args__ = (
        Index("ix_node_dep_source", "source_node_id"),
        Index("ix_node_dep_target", "target_node_id"),
        UniqueConstraint(
            "source_node_id", "target_node_id", "dependency_type", name="uq_node_dependency"
        ),
    )

    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False
    )
    dependency_type: Mapped[str] = mapped_column(String(32), nullable=False, default="requires")


class LearningPath(UUIDPKMixin, Base):
    __tablename__ = "learning_paths"

    course_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(48), nullable=False, default="default")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


# ── Skills & outcomes ────────────────────────────────────────────────────────


class Skill(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    framework: Mapped[str | None] = mapped_column(String(120), nullable=True)
    competency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competencies.id", ondelete="SET NULL"), nullable=True
    )


class Competency(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "competencies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)


class LearningOutcome(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "learning_outcomes"

    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="CLO")
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)


class NodeSkill(UUIDPKMixin, Base):
    __tablename__ = "node_skills"
    __table_args__ = (UniqueConstraint("node_id", "skill_id", name="uq_node_skill"),)

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )


class OutcomeMapping(UUIDPKMixin, Base):
    __tablename__ = "outcome_mappings"

    outcome_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_outcomes.id", ondelete="CASCADE"), nullable=False
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=True
    )
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=True
    )
    coverage_level: Mapped[str] = mapped_column(String(32), nullable=False, default="introduced")


__all__ = [
    "Course",
    "CourseVersion",
    "LearningNode",
    "NodeDependency",
    "LearningPath",
    "Skill",
    "Competency",
    "LearningOutcome",
    "NodeSkill",
    "OutcomeMapping",
]
