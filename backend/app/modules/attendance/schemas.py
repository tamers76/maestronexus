"""Attendance request/response schemas (docs/09, docs/13)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AttendanceStatus = Literal["present", "absent", "late", "excused"]
SessionMode = Literal["in_person", "online", "hybrid"]


# ── Class (lightweight helper for class selection) ───────────────────────────


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    course_id: uuid.UUID


# ── Session ──────────────────────────────────────────────────────────────────


class SessionCreate(BaseModel):
    class_id: uuid.UUID
    scheduled_at: datetime
    mode: SessionMode = "in_person"


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    class_id: uuid.UUID
    scheduled_at: datetime
    mode: str
    created_at: datetime
    updated_at: datetime


# ── Records ──────────────────────────────────────────────────────────────────


class RecordIn(BaseModel):
    learner_id: uuid.UUID
    status: AttendanceStatus


class RecordsBulkIn(BaseModel):
    records: list[RecordIn] = Field(default_factory=list)


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    learner_id: uuid.UUID
    status: str
    marked_at: datetime | None
    marked_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class RosterEntry(BaseModel):
    """A learner in the session's class, merged with their current mark (if any)."""

    learner_id: uuid.UUID
    display_name: str
    email: str
    status: str | None
    marked_at: datetime | None
