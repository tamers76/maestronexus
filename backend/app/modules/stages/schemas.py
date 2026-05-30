"""Stage module request/response schemas (docs/13)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StageCatalogItem(BaseModel):
    key: str
    order: int
    title: str
    description: str
    inputs: list[str]
    output_kind: str
    default_execution: str
    risk: str
    promotes_to: str | None = None
    aliases: list[str] = Field(default_factory=list)


class StageRunSummary(BaseModel):
    id: uuid.UUID
    status: str
    execution_mode: str
    review_status: str
    risk_score: float
    stubbed: bool = False
    created_at: datetime
    updated_at: datetime


class StageStatus(BaseModel):
    """A stage's catalog metadata + its latest run on a given course."""

    key: str
    order: int
    title: str
    description: str
    risk: str
    default_execution: str
    promotes_to: str | None = None
    aliases: list[str] = Field(default_factory=list)
    last_run: StageRunSummary | None = None


class StageRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    course_version_id: uuid.UUID | None
    stage_key: str
    status: str
    execution_mode: str
    input_refs: dict
    output: dict
    council_transcript: dict
    risk_score: float
    review_status: str
    created_at: datetime
    updated_at: datetime


class RunStageRequest(BaseModel):
    # Per-run override of the configured execution mode.
    mode: str | None = Field(default=None, pattern="^(single|council)$")
    course_version_id: uuid.UUID | None = None
    # Free-form options forwarded to the prompt builder (e.g. syllabus_text,
    # storage_key, instructions).
    options: dict[str, Any] = Field(default_factory=dict)


class ReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class ApprovedArtifactOut(BaseModel):
    """The current approved design artifact for a stage on a course."""

    stage_key: str
    source: str  # "design_artifact" | "stage_run"
    review_status: str
    course_version_id: uuid.UUID | None = None
    source_run_id: uuid.UUID | None = None
    artifact: Any | None = None
    updated_at: str


__all__ = [
    "StageCatalogItem",
    "StageRunSummary",
    "StageStatus",
    "StageRunOut",
    "RunStageRequest",
    "ReviewRequest",
    "ApprovedArtifactOut",
]
