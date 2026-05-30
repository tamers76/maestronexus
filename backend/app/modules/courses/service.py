"""Courses / Learning Graph service layer (docs/04, docs/11).

All DB and business logic lives here so the router stays a thin HTTP shell. Every
loader enforces tenant isolation by resolving ownership back to ``Course.tenant_id``
(versions/nodes/dependencies have no ``tenant_id`` column of their own).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Principal, ensure_same_tenant
from app.modules.courses.models import (
    Course,
    CourseVersion,
    LearningNode,
    NodeDependency,
)
from app.modules.courses.schemas import (
    CourseCreate,
    CourseUpdate,
    CourseVersionCreate,
    GraphEdge,
    GraphNode,
    GraphResponse,
    LearningNodeCreate,
    LearningNodeOut,
    LearningNodeUpdate,
    NodeDependencyCreate,
    Position,
)

# Statuses considered "removed" for soft delete (Course has no deleted_at column).
_ARCHIVED_STATUS = "archived"


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


# ── Loaders (tenant-scoped) ──────────────────────────────────────────────────


async def load_course(session: AsyncSession, user: Principal, course_id: uuid.UUID) -> Course:
    course = await session.get(Course, course_id)
    if course is None or course.status == _ARCHIVED_STATUS:
        raise _not_found("Course")
    ensure_same_tenant(user, course.tenant_id)
    return course


async def load_version(
    session: AsyncSession, user: Principal, version_id: uuid.UUID
) -> tuple[CourseVersion, Course]:
    version = await session.get(CourseVersion, version_id)
    if version is None:
        raise _not_found("Course version")
    course = await load_course(session, user, version.course_id)
    return version, course


async def load_node(
    session: AsyncSession, user: Principal, node_id: uuid.UUID
) -> tuple[LearningNode, CourseVersion, Course]:
    node = await session.get(LearningNode, node_id)
    if node is None:
        raise _not_found("Learning node")
    version, course = await load_version(session, user, node.course_version_id)
    return node, version, course


# ── Course CRUD ──────────────────────────────────────────────────────────────


async def create_course(session: AsyncSession, user: Principal, payload: CourseCreate) -> Course:
    course = Course(
        tenant_id=user.tenant_id,
        created_by=user.id,
        title=payload.title,
        description=payload.description,
        program_id=payload.program_id,
        status="draft",
    )
    session.add(course)
    await session.flush()
    return course


async def list_courses(
    session: AsyncSession, user: Principal, *, limit: int, offset: int
) -> tuple[list[Course], int]:
    base = select(Course).where(
        Course.tenant_id == user.tenant_id,
        Course.status != _ARCHIVED_STATUS,
    )
    total = (
        await session.execute(
            select(func.count()).select_from(base.order_by(None).subquery())
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                base.order_by(Course.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


async def update_course(
    session: AsyncSession, user: Principal, course_id: uuid.UUID, payload: CourseUpdate
) -> Course:
    course = await load_course(session, user, course_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(course, field, value)
    await session.flush()
    # Reload the server-side ``updated_at`` (onupdate) within the async context.
    await session.refresh(course)
    return course


async def soft_delete_course(
    session: AsyncSession, user: Principal, course_id: uuid.UUID
) -> Course:
    course = await load_course(session, user, course_id)
    course.status = _ARCHIVED_STATUS
    await session.flush()
    return course


# ── Course versions ──────────────────────────────────────────────────────────


async def _latest_version(
    session: AsyncSession, course_id: uuid.UUID
) -> CourseVersion | None:
    return (
        await session.execute(
            select(CourseVersion)
            .where(CourseVersion.course_id == course_id)
            .order_by(CourseVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _clone_graph(
    session: AsyncSession, src_version_id: uuid.UUID, dst_version: CourseVersion
) -> None:
    """Copy nodes + dependencies from ``src`` into a fresh draft version."""
    nodes = (
        (
            await session.execute(
                select(LearningNode).where(LearningNode.course_version_id == src_version_id)
            )
        )
        .scalars()
        .all()
    )
    id_map: dict[uuid.UUID, uuid.UUID] = {}
    for src in nodes:
        clone = LearningNode(
            course_version_id=dst_version.id,
            type=src.type,
            title=src.title,
            learning_objective=dict(src.learning_objective),
            mastery_rule=dict(src.mastery_rule),
            completion_rule=dict(src.completion_rule),
            estimated_duration=src.estimated_duration,
            node_metadata=dict(src.node_metadata),
        )
        session.add(clone)
        await session.flush()
        id_map[src.id] = clone.id

    deps = (
        (
            await session.execute(
                select(NodeDependency).where(
                    NodeDependency.source_node_id.in_(list(id_map.keys()))
                )
            )
        )
        .scalars()
        .all()
    )
    for dep in deps:
        if dep.source_node_id in id_map and dep.target_node_id in id_map:
            session.add(
                NodeDependency(
                    source_node_id=id_map[dep.source_node_id],
                    target_node_id=id_map[dep.target_node_id],
                    dependency_type=dep.dependency_type,
                )
            )
    await session.flush()


async def create_version(
    session: AsyncSession,
    user: Principal,
    course_id: uuid.UUID,
    payload: CourseVersionCreate,
) -> CourseVersion:
    await load_course(session, user, course_id)
    latest = await _latest_version(session, course_id)
    next_number = (latest.version + 1) if latest else 1
    version = CourseVersion(
        course_id=course_id,
        version=next_number,
        state="draft",
        created_by=user.id,
    )
    session.add(version)
    await session.flush()
    if payload.clone_from_latest and latest is not None:
        await _clone_graph(session, latest.id, version)
    return version


async def list_versions(
    session: AsyncSession, user: Principal, course_id: uuid.UUID
) -> list[CourseVersion]:
    await load_course(session, user, course_id)
    rows = (
        (
            await session.execute(
                select(CourseVersion)
                .where(CourseVersion.course_id == course_id)
                .order_by(CourseVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def publish_version(
    session: AsyncSession, user: Principal, version_id: uuid.UUID
) -> CourseVersion:
    version, course = await load_version(session, user, version_id)
    if version.state == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Version already published"
        )
    node_count = (
        await session.execute(
            select(func.count())
            .select_from(LearningNode)
            .where(LearningNode.course_version_id == version_id)
        )
    ).scalar_one()
    if node_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot publish a version with no learning nodes",
        )
    version.state = "published"
    version.published_at = datetime.now(UTC)
    # Flip the course out of draft once it has a published version.
    if course.status == "draft":
        course.status = "published"
    await session.flush()
    await session.refresh(version)
    return version


# ── Learning nodes ───────────────────────────────────────────────────────────


def _node_metadata_with_position(base: dict, position: Position) -> dict:
    meta = dict(base or {})
    meta["position"] = {"x": position.x, "y": position.y}
    return meta


def node_to_out(node: LearningNode) -> LearningNodeOut:
    pos = (node.node_metadata or {}).get("position") or {}
    return LearningNodeOut(
        id=node.id,
        course_version_id=node.course_version_id,
        type=node.type,
        title=node.title,
        learning_objective=node.learning_objective,
        mastery_rule=node.mastery_rule,
        completion_rule=node.completion_rule,
        estimated_duration=node.estimated_duration,
        position=Position(x=pos.get("x", 0.0), y=pos.get("y", 0.0)),
        node_metadata=node.node_metadata or {},
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


async def create_node(
    session: AsyncSession,
    user: Principal,
    version_id: uuid.UUID,
    payload: LearningNodeCreate,
) -> LearningNode:
    version, _ = await load_version(session, user, version_id)
    if version.state == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit a published version; create a new version first",
        )
    node = LearningNode(
        course_version_id=version_id,
        type=payload.type,
        title=payload.title,
        learning_objective=payload.learning_objective,
        mastery_rule=payload.mastery_rule,
        completion_rule=payload.completion_rule,
        estimated_duration=payload.estimated_duration,
        node_metadata=_node_metadata_with_position({}, payload.position),
    )
    session.add(node)
    await session.flush()
    return node


async def list_nodes(
    session: AsyncSession, user: Principal, version_id: uuid.UUID
) -> list[LearningNode]:
    await load_version(session, user, version_id)
    rows = (
        (
            await session.execute(
                select(LearningNode)
                .where(LearningNode.course_version_id == version_id)
                .order_by(LearningNode.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def update_node(
    session: AsyncSession,
    user: Principal,
    node_id: uuid.UUID,
    payload: LearningNodeUpdate,
) -> LearningNode:
    node, version, _ = await load_node(session, user, node_id)
    if version.state == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit a published version; create a new version first",
        )
    data = payload.model_dump(exclude_unset=True)
    position = data.pop("position", None)
    for field, value in data.items():
        setattr(node, field, value)
    if position is not None:
        node.node_metadata = _node_metadata_with_position(
            node.node_metadata, Position(**position)
        )
    await session.flush()
    await session.refresh(node)
    return node


async def delete_node(session: AsyncSession, user: Principal, node_id: uuid.UUID) -> None:
    node, version, _ = await load_node(session, user, node_id)
    if version.state == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit a published version; create a new version first",
        )
    await session.delete(node)
    await session.flush()


# ── Dependencies (edges) ─────────────────────────────────────────────────────


async def _version_edges(
    session: AsyncSession, version_id: uuid.UUID
) -> list[NodeDependency]:
    node_ids = (
        select(LearningNode.id).where(LearningNode.course_version_id == version_id).subquery()
    )
    rows = (
        (
            await session.execute(
                select(NodeDependency).where(
                    NodeDependency.source_node_id.in_(select(node_ids.c.id))
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


def _creates_cycle(
    edges: list[NodeDependency], source: uuid.UUID, target: uuid.UUID
) -> bool:
    """True if adding source->target introduces a directed cycle.

    Edge ``s->t`` means ``t`` depends on ``s`` (s is a prerequisite of t). A cycle
    exists if ``target`` can already reach ``source`` following existing edges.
    """
    if source == target:
        return True
    adjacency: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for edge in edges:
        adjacency[edge.source_node_id].append(edge.target_node_id)

    stack = [target]
    seen: set[uuid.UUID] = set()
    while stack:
        current = stack.pop()
        if current == source:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(adjacency.get(current, []))
    return False


async def create_dependency(
    session: AsyncSession,
    user: Principal,
    version_id: uuid.UUID,
    payload: NodeDependencyCreate,
) -> NodeDependency:
    version, _ = await load_version(session, user, version_id)
    if version.state == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit a published version; create a new version first",
        )

    nodes = await list_nodes(session, user, version_id)
    node_ids = {n.id for n in nodes}
    if payload.source_node_id not in node_ids or payload.target_node_id not in node_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both nodes must belong to this course version",
        )

    edges = await _version_edges(session, version_id)
    if any(
        e.source_node_id == payload.source_node_id
        and e.target_node_id == payload.target_node_id
        and e.dependency_type == payload.dependency_type
        for e in edges
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Dependency already exists"
        )
    if _creates_cycle(edges, payload.source_node_id, payload.target_node_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dependency would create a cycle in the learning graph",
        )

    dep = NodeDependency(
        source_node_id=payload.source_node_id,
        target_node_id=payload.target_node_id,
        dependency_type=payload.dependency_type,
    )
    session.add(dep)
    await session.flush()
    return dep


async def delete_dependency(
    session: AsyncSession, user: Principal, dependency_id: uuid.UUID
) -> None:
    dep = await session.get(NodeDependency, dependency_id)
    if dep is None:
        raise _not_found("Dependency")
    # Authorize via the source node's owning course/tenant.
    await load_node(session, user, dep.source_node_id)
    await session.delete(dep)
    await session.flush()


# ── Graph projection (React Flow) ────────────────────────────────────────────


async def get_graph(
    session: AsyncSession, user: Principal, version_id: uuid.UUID
) -> GraphResponse:
    version, _ = await load_version(session, user, version_id)
    nodes = await list_nodes(session, user, version_id)
    edges = await _version_edges(session, version_id)

    graph_nodes = [
        GraphNode(
            id=str(n.id),
            position=node_to_out(n).position,
            data={
                "label": n.title,
                "nodeType": n.type,
                "estimatedDuration": n.estimated_duration,
                "learningObjective": n.learning_objective,
                "masteryRule": n.mastery_rule,
                "completionRule": n.completion_rule,
            },
        )
        for n in nodes
    ]
    graph_edges = [
        GraphEdge(
            id=str(e.id),
            source=str(e.source_node_id),
            target=str(e.target_node_id),
            label=e.dependency_type.replace("_", " "),
            data={"dependencyType": e.dependency_type},
        )
        for e in edges
    ]
    return GraphResponse(
        version=version,  # type: ignore[arg-type]
        nodes=graph_nodes,
        edges=graph_edges,
    )
