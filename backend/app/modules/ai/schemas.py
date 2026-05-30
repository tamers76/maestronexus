"""AI module request/response schemas (docs/06, docs/13)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Tutor ─────────────────────────────────────────────────────────────────────


class TutorSource(BaseModel):
    """A grounding citation surfaced alongside a tutor answer."""

    content_item_id: uuid.UUID
    node_id: uuid.UUID
    title: str
    snippet: str


class TutorRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    # Optional context references to scope retrieval (docs/06).
    node_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    # Optional assessment reference — forces the graded-content guardrail.
    assessment_id: uuid.UUID | None = None


class TutorResponse(BaseModel):
    interaction_id: uuid.UUID
    answer: str
    grounded: bool
    refused: bool
    escalate: bool
    escalation_path: str
    sources: list[TutorSource]
    provider: str
    model: str
    stubbed: bool


# ── Content draft ─────────────────────────────────────────────────────────────


class DraftCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    title: str | None = Field(default=None, max_length=255)
    modality: str = Field(default="text", max_length=48)
    objectives: list[str] = Field(default_factory=list)
    # Optionally ground the draft in approved content for a node.
    node_id: uuid.UUID | None = None
    instructions: str | None = Field(default=None, max_length=2000)


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    interaction_id: uuid.UUID | None
    target_type: str
    review_status: str
    draft: dict
    created_at: datetime
    updated_at: datetime


class DraftListParams(BaseModel):
    review_status: str | None = Field(default=None, max_length=32)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
