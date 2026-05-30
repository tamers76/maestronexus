"""Enrollment & progress request/response schemas (docs/05, docs/12, docs/13)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Classes ──────────────────────────────────────────────────────────────────


class ClassCreate(BaseModel):
    course_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    teacher_id: uuid.UUID | None = None


class ClassUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    teacher_id: uuid.UUID | None = None


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    course_id: uuid.UUID
    teacher_id: uuid.UUID | None
    name: str
    created_at: datetime


# ── Course / version pickers (read-only helper for the UI) ───────────────────


class CourseVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    state: str


class CourseOut(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    versions: list[CourseVersionOut]


# ── Enrollments ──────────────────────────────────────────────────────────────


class EnrollmentCreate(BaseModel):
    """Enroll a learner into a class, pinned to a course version.

    Provide either ``user_id`` or ``email`` to identify the learner. When
    ``course_version_id`` is omitted the latest published version of the class's
    course is used.
    """

    class_id: uuid.UUID
    user_id: uuid.UUID | None = None
    email: str | None = None
    course_version_id: uuid.UUID | None = None


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    class_id: uuid.UUID
    course_version_id: uuid.UUID
    status: str
    created_at: datetime


class NodeProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    node_id: uuid.UUID
    node_title: str
    node_type: str
    state: str
    attempts: int
    time_spent_seconds: int
    confidence: float | None
    completed_at: datetime | None


class NodeEdgeOut(BaseModel):
    """A dependency edge in the pinned version's graph (for rendering)."""

    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    dependency_type: str


class EnrollmentDetail(BaseModel):
    enrollment: EnrollmentOut
    class_name: str
    learner_name: str
    nodes: list[NodeProgressOut]
    edges: list[NodeEdgeOut]


class CompleteNodeRequest(BaseModel):
    """Signals reported when a learner finishes a node."""

    score: float | None = Field(default=None, ge=0.0, le=1.0)
    time_spent_seconds: int = Field(default=0, ge=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class CompleteNodeResult(BaseModel):
    node: NodeProgressOut
    unlocked_node_ids: list[uuid.UUID]
    mastered: bool
