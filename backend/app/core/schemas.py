"""Shared API schema conventions (docs/13).

Modules should reuse these so list endpoints and error envelopes stay consistent
across the whole API surface.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    """Standard paginated list envelope."""

    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams(BaseModel):
    """Common pagination query params (use as a FastAPI dependency)."""

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class Message(BaseModel):
    """Simple acknowledgement payload."""

    message: str
