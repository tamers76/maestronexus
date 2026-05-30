"""Adaptive engine request/response schemas (docs/05, docs/13)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class NextNodeResponse(BaseModel):
    """The current top recommendation for an enrollment.

    ``recommended_node_id`` is ``None`` when the course is complete (or no node
    is currently available); ``reason`` is always a human-readable explanation.
    """

    recommendation_id: uuid.UUID | None = None
    recommended_node_id: uuid.UUID | None = None
    node_title: str | None = None
    node_type: str | None = None
    reason: str
    source: str | None = None  # "engine" | "teacher_override"
    course_complete: bool = False


class OverrideRequest(BaseModel):
    """Teacher assignment that overrides the engine's suggestion (docs/05)."""

    node_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=2000)
