"""Projects request/response schemas (docs/08, docs/13)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Project ──────────────────────────────────────────────────────────────────


class ProjectCreate(BaseModel):
    node_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    instructions: dict = Field(default_factory=dict)
    collaborative: bool = False
    # 0 (or negative) means unlimited attempts; otherwise a hard cap (docs/08).
    max_submissions: int = Field(default=1, ge=0)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    instructions: dict | None = None
    collaborative: bool | None = None
    max_submissions: int | None = Field(default=None, ge=0)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    node_id: uuid.UUID
    title: str
    instructions: dict
    collaborative: bool
    max_submissions: int
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ── Rubric ───────────────────────────────────────────────────────────────────


class RubricIn(BaseModel):
    """Free-form weighted criteria, e.g. ``{"items": [{"key", "label", "max"}]}``."""

    criteria: dict = Field(default_factory=dict)


class RubricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    criteria: dict
    created_at: datetime
    updated_at: datetime


# ── Submission ─────────────────────────────────────────────────────────────


class SubmissionCreate(BaseModel):
    payload: dict = Field(default_factory=dict)


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    learner_id: uuid.UUID
    attempt_no: int
    status: str
    payload: dict
    created_at: datetime
    updated_at: datetime


class SubmissionListItem(BaseModel):
    """A row in the teacher grading queue (own-class submissions only)."""

    id: uuid.UUID
    project_id: uuid.UUID
    project_title: str
    learner_id: uuid.UUID
    learner_name: str
    class_id: uuid.UUID
    class_name: str
    attempt_no: int
    status: str
    graded: bool
    score: float | None
    created_at: datetime


# ── Grade + Feedback ─────────────────────────────────────────────────────────


class GradeIn(BaseModel):
    score: float | None = None
    rubric_scores: dict = Field(default_factory=dict)
    feedback: str = ""


class GradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID
    grader_id: uuid.UUID | None
    score: float | None
    rubric_scores: dict
    created_at: datetime
    updated_at: datetime


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    grade_id: uuid.UUID
    author_type: str
    body: str
    created_at: datetime
    updated_at: datetime


class GradeResult(BaseModel):
    grade: GradeOut
    feedback: FeedbackOut | None


class SubmissionDetail(BaseModel):
    """Everything the grading view needs for one submission."""

    submission: SubmissionOut
    project: ProjectOut
    learner_name: str
    class_id: uuid.UUID
    class_name: str
    rubric: RubricOut | None
    grade: GradeOut | None
    feedback: FeedbackOut | None
