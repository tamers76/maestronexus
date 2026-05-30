"""Integrations / AI settings schemas (docs/10, docs/13)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AiSettingsResponse(BaseModel):
    """Full settings view for the admin UI: masked config + metadata + preview."""

    config: dict[str, Any]
    catalog: list[dict[str, Any]]
    resolved: list[dict[str, Any]]
    recommended_prompts: dict[str, dict[str, str]]
    managed_providers: list[str]


class AiSettingsUpdate(BaseModel):
    """Partial, deep-merged update. Masked api_key values are ignored server-side."""

    providers: dict[str, Any] | None = None
    council: dict[str, Any] | None = None
    stages: dict[str, Any] | None = None


class TestConnectionRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=64)


class TestConnectionResponse(BaseModel):
    success: bool
    message: str


class ModelOption(BaseModel):
    id: str
    name: str


__all__ = [
    "AiSettingsResponse",
    "AiSettingsUpdate",
    "TestConnectionRequest",
    "TestConnectionResponse",
    "ModelOption",
]
