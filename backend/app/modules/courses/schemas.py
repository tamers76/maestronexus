"""Courses / Learning Graph request & response schemas (docs/04, docs/13).

Shapes the course graph (courses -> versions -> nodes -> dependencies) plus a
React-Flow-friendly graph projection. Reuses ``app.core.schemas.Page`` for lists.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Dependency types the editor may draw (docs/04 — MVP subset).
DependencyType = Literal["requires", "mastery_gate"]

# ── Courses ──────────────────────────────────────────────────────────────────


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    program_id: uuid.UUID | None = None


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, max_length=32)
    program_id: uuid.UUID | None = None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    program_id: uuid.UUID | None
    title: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


# ── Course versions ──────────────────────────────────────────────────────────


class CourseVersionCreate(BaseModel):
    # Clone the latest version's graph into the new draft so designers can iterate
    # on a published snapshot without starting from scratch (docs/04 versioning).
    clone_from_latest: bool = True


class CourseVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    version: int
    state: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ── Learning nodes ───────────────────────────────────────────────────────────


class Position(BaseModel):
    """React Flow canvas coordinates, persisted in ``node_metadata``."""

    x: float = 0.0
    y: float = 0.0


class LearningNodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    type: str = Field(default="lesson", max_length=48)
    learning_objective: dict = Field(default_factory=dict)
    mastery_rule: dict = Field(default_factory=dict)
    completion_rule: dict = Field(default_factory=dict)
    estimated_duration: int | None = Field(default=None, ge=0)
    position: Position = Field(default_factory=Position)


class LearningNodeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    type: str | None = Field(default=None, max_length=48)
    learning_objective: dict | None = None
    mastery_rule: dict | None = None
    completion_rule: dict | None = None
    estimated_duration: int | None = Field(default=None, ge=0)
    position: Position | None = None


class LearningNodeOut(BaseModel):
    id: uuid.UUID
    course_version_id: uuid.UUID
    type: str
    title: str
    learning_objective: dict
    mastery_rule: dict
    completion_rule: dict
    estimated_duration: int | None
    position: Position
    node_metadata: dict
    created_at: datetime
    updated_at: datetime


# ── Node dependencies (edges) ────────────────────────────────────────────────


class NodeDependencyCreate(BaseModel):
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    dependency_type: DependencyType = "requires"


class NodeDependencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    dependency_type: str


# ── React Flow graph projection ──────────────────────────────────────────────


class GraphNode(BaseModel):
    """A node shaped for ``@xyflow/react`` (``type`` is the RF component key)."""

    id: str
    type: str = "learning"
    position: Position
    data: dict


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str = "smoothstep"
    label: str | None = None
    data: dict


class GraphResponse(BaseModel):
    version: CourseVersionOut
    nodes: list[GraphNode]
    edges: list[GraphEdge]
