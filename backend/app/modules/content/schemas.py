"""Content & assessment request/response schemas (docs/07, docs/13).

The cardinal rule encoded here: ``answer_key`` is *never* exposed on a
learner-facing schema. Authoring schemas (``QuestionOut``) carry it; learner
schemas (``QuestionLearnerOut``) deliberately omit it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Modalities and statuses kept as plain strings (validated softly) to match the
# flexible String columns in the data model (docs/12).
APPROVAL_STATUSES = ("draft", "in_review", "approved", "archived")


# ── Content items ────────────────────────────────────────────────────────────


class ContentItemCreate(BaseModel):
    node_id: uuid.UUID
    modality: str = Field(default="text", max_length=48)
    body: dict = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)


class ContentItemUpdate(BaseModel):
    modality: str | None = Field(default=None, max_length=48)
    body: dict | None = None


class ContentItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    node_id: uuid.UUID
    modality: str
    version: int
    body: dict
    approval_status: str
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ── Media assets ─────────────────────────────────────────────────────────────


class MediaAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    storage_key: str
    mime_type: str
    size_bytes: int
    content_item_id: uuid.UUID | None
    created_at: datetime


class MediaUploadRequest(BaseModel):
    """Server-side upload payload.

    Bytes arrive base64-encoded in JSON so the endpoint needs no multipart
    dependency; the server decodes and writes them to object storage.
    """

    filename: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(default="application/octet-stream", max_length=255)
    content_base64: str = Field(min_length=1)
    content_item_id: uuid.UUID | None = None


class MediaDownloadOut(BaseModel):
    asset: MediaAssetOut
    download_url: str


class PresignUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(default="application/octet-stream", max_length=255)
    content_item_id: uuid.UUID | None = None


class PresignUploadOut(BaseModel):
    asset: MediaAssetOut
    upload_url: str


# ── Assessments & questions ──────────────────────────────────────────────────


class AssessmentCreate(BaseModel):
    node_id: uuid.UUID
    type: str = Field(default="quiz", max_length=48)
    config: dict = Field(default_factory=dict)


class AssessmentUpdate(BaseModel):
    type: str | None = Field(default=None, max_length=48)
    config: dict | None = None


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    node_id: uuid.UUID
    type: str
    config: dict
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class QuestionCreate(BaseModel):
    type: str = Field(default="mcq", max_length=48)
    prompt: dict = Field(default_factory=dict)
    answer_key: dict = Field(default_factory=dict)
    position: int = Field(default=0, ge=0)


class QuestionUpdate(BaseModel):
    type: str | None = Field(default=None, max_length=48)
    prompt: dict | None = None
    answer_key: dict | None = None
    position: int | None = Field(default=None, ge=0)


class QuestionOut(BaseModel):
    """Authoring view — includes ``answer_key`` (authors only)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    type: str
    prompt: dict
    answer_key: dict
    position: int


class QuestionLearnerOut(BaseModel):
    """Learner view — ``answer_key`` is intentionally absent."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    type: str
    prompt: dict
    position: int


class AssessmentDetailOut(AssessmentOut):
    """Authoring detail: assessment plus full questions (with answer keys)."""

    questions: list[QuestionOut] = Field(default_factory=list)


class AssessmentLearnerOut(BaseModel):
    """Learner-facing quiz: questions stripped of answer keys."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    node_id: uuid.UUID
    type: str
    config: dict
    questions: list[QuestionLearnerOut] = Field(default_factory=list)


# ── Attempts ─────────────────────────────────────────────────────────────────


class AttemptCreate(BaseModel):
    enrollment_id: uuid.UUID
    assessment_id: uuid.UUID
    # Map of question id (string) -> learner response (scalar or list).
    responses: dict = Field(default_factory=dict)


class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    enrollment_id: uuid.UUID
    assessment_id: uuid.UUID
    score: float | None
    responses: dict
    submitted_at: datetime | None
