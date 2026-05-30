"""Enrollment & progress service (docs/04, docs/05, docs/12).

Holds the business logic kept out of the router: class CRUD, enrolling a learner
(pinned to an immutable ``course_version``), initializing per-node progress, and
the node state machine ``locked → available → completed → mastered``.

Dependency semantics (docs/04):
  * ``requires``      — target is locked until the source node is *completed*.
  * ``mastery_gate``  — target is locked until the source node is *mastered*.
Other edge types (``optional``/``parallel``) never lock a node.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Principal, ensure_same_tenant
from app.modules.courses.models import Course, CourseVersion, LearningNode, NodeDependency
from app.modules.enrollment.models import Class, Enrollment, MasteryRecord, NodeProgress
from app.modules.iam.models import User

# Edge types that gate availability.
_LOCKING_EDGES = ("requires", "mastery_gate")
_COMPLETED_STATES = ("completed", "mastered")
# Default mastery bar when a node declares no explicit rule (docs/05).
DEFAULT_MASTERY_THRESHOLD = 0.8


# ── Classes ──────────────────────────────────────────────────────────────────


async def create_class(
    session: AsyncSession, user: Principal, *, course_id: uuid.UUID, name: str,
    teacher_id: uuid.UUID | None,
) -> Class:
    course = await session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    ensure_same_tenant(user, course.tenant_id)

    obj = Class(
        tenant_id=user.tenant_id,
        course_id=course_id,
        teacher_id=teacher_id,
        name=name,
    )
    session.add(obj)
    await session.flush()
    return obj


async def list_classes(
    session: AsyncSession, user: Principal, *, limit: int, offset: int,
    teacher_id: uuid.UUID | None = None,
) -> tuple[list[Class], int]:
    stmt = select(Class).where(Class.tenant_id == user.tenant_id)
    if teacher_id is not None:
        stmt = stmt.where(Class.teacher_id == teacher_id)
    count_stmt = select(Class.id).where(Class.tenant_id == user.tenant_id)
    if teacher_id is not None:
        count_stmt = count_stmt.where(Class.teacher_id == teacher_id)
    total = len((await session.execute(count_stmt)).scalars().all())
    rows = (
        (
            await session.execute(
                stmt.order_by(Class.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


async def get_class(session: AsyncSession, user: Principal, class_id: uuid.UUID) -> Class:
    obj = await session.get(Class, class_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    ensure_same_tenant(user, obj.tenant_id)
    return obj


async def update_class(
    session: AsyncSession, user: Principal, class_id: uuid.UUID, *,
    name: str | None, teacher_id: uuid.UUID | None,
) -> Class:
    obj = await get_class(session, user, class_id)
    if name is not None:
        obj.name = name
    if teacher_id is not None:
        obj.teacher_id = teacher_id
    await session.flush()
    return obj


# ── Course pickers (read-only) ───────────────────────────────────────────────


async def list_courses_with_versions(
    session: AsyncSession, user: Principal
) -> list[tuple[Course, list[CourseVersion]]]:
    """Read-only helper that powers the create-class / pin-version UI."""

    courses = (
        (
            await session.execute(
                select(Course)
                .where(Course.tenant_id == user.tenant_id)
                .order_by(Course.title)
            )
        )
        .scalars()
        .all()
    )
    out: list[tuple[Course, list[CourseVersion]]] = []
    for course in courses:
        versions = (
            (
                await session.execute(
                    select(CourseVersion)
                    .where(CourseVersion.course_id == course.id)
                    .order_by(CourseVersion.version.desc())
                )
            )
            .scalars()
            .all()
        )
        out.append((course, list(versions)))
    return out


# ── Enrollment ───────────────────────────────────────────────────────────────


async def _resolve_learner(
    session: AsyncSession, user: Principal, *, user_id: uuid.UUID | None, email: str | None
) -> User:
    learner: User | None = None
    if user_id is not None:
        learner = await session.get(User, user_id)
    elif email is not None:
        learner = (
            await session.execute(
                select(User).where(
                    User.tenant_id == user.tenant_id,
                    User.email == email,
                    User.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either user_id or email",
        )
    if learner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found")
    ensure_same_tenant(user, learner.tenant_id)
    return learner


async def _resolve_version(
    session: AsyncSession, course_id: uuid.UUID, course_version_id: uuid.UUID | None
) -> CourseVersion:
    if course_version_id is not None:
        version = await session.get(CourseVersion, course_version_id)
        if version is None or version.course_id != course_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course version not found for this course",
            )
        return version

    # No pin supplied: prefer the latest published version, else the latest.
    published = (
        await session.execute(
            select(CourseVersion)
            .where(CourseVersion.course_id == course_id, CourseVersion.state == "published")
            .order_by(CourseVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if published is not None:
        return published

    latest = (
        await session.execute(
            select(CourseVersion)
            .where(CourseVersion.course_id == course_id)
            .order_by(CourseVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course has no versions to enroll into",
        )
    return latest


async def _incoming_locking_deps(
    session: AsyncSession, node_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[NodeDependency]]:
    """Map each node -> its incoming locking dependency edges (requires/mastery_gate)."""
    if not node_ids:
        return {}
    deps = (
        (
            await session.execute(
                select(NodeDependency).where(
                    NodeDependency.target_node_id.in_(node_ids),
                    NodeDependency.dependency_type.in_(_LOCKING_EDGES),
                )
            )
        )
        .scalars()
        .all()
    )
    by_target: dict[uuid.UUID, list[NodeDependency]] = {nid: [] for nid in node_ids}
    for dep in deps:
        by_target.setdefault(dep.target_node_id, []).append(dep)
    return by_target


def _prereqs_met(
    deps: list[NodeDependency], state_by_node: dict[uuid.UUID, str]
) -> bool:
    for dep in deps:
        src_state = state_by_node.get(dep.source_node_id)
        if dep.dependency_type == "mastery_gate":
            if src_state != "mastered":
                return False
        else:  # requires
            if src_state not in _COMPLETED_STATES:
                return False
    return True


async def enroll_learner(
    session: AsyncSession, user: Principal, *,
    class_id: uuid.UUID, user_id: uuid.UUID | None, email: str | None,
    course_version_id: uuid.UUID | None,
) -> Enrollment:
    klass = await get_class(session, user, class_id)
    learner = await _resolve_learner(session, user, user_id=user_id, email=email)
    version = await _resolve_version(session, klass.course_id, course_version_id)

    existing = (
        await session.execute(
            select(Enrollment).where(
                Enrollment.user_id == learner.id,
                Enrollment.class_id == class_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Learner is already enrolled in this class",
        )

    enrollment = Enrollment(
        tenant_id=klass.tenant_id,
        user_id=learner.id,
        class_id=class_id,
        course_version_id=version.id,
        status="active",
    )
    session.add(enrollment)
    await session.flush()

    await _initialize_progress(session, enrollment)
    return enrollment


async def _initialize_progress(session: AsyncSession, enrollment: Enrollment) -> None:
    nodes = (
        (
            await session.execute(
                select(LearningNode).where(
                    LearningNode.course_version_id == enrollment.course_version_id
                )
            )
        )
        .scalars()
        .all()
    )
    node_ids = [n.id for n in nodes]
    deps_by_target = await _incoming_locking_deps(session, node_ids)
    for node in nodes:
        has_prereqs = bool(deps_by_target.get(node.id))
        session.add(
            NodeProgress(
                enrollment_id=enrollment.id,
                node_id=node.id,
                state="locked" if has_prereqs else "available",
            )
        )
    await session.flush()


async def list_enrollments(
    session: AsyncSession, user: Principal, *,
    class_id: uuid.UUID | None, user_id: uuid.UUID | None, limit: int, offset: int,
) -> tuple[list[Enrollment], int]:
    stmt = select(Enrollment).where(
        Enrollment.tenant_id == user.tenant_id, Enrollment.deleted_at.is_(None)
    )
    if class_id is not None:
        stmt = stmt.where(Enrollment.class_id == class_id)
    if user_id is not None:
        stmt = stmt.where(Enrollment.user_id == user_id)
    rows = (
        (await session.execute(stmt.order_by(Enrollment.created_at.desc())))
        .scalars()
        .all()
    )
    total = len(rows)
    return list(rows[offset : offset + limit]), total


async def get_enrollment(
    session: AsyncSession, user: Principal, enrollment_id: uuid.UUID
) -> Enrollment:
    obj = await session.get(Enrollment, enrollment_id)
    if obj is None or obj.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    ensure_same_tenant(user, obj.tenant_id)
    return obj


async def node_progress_rows(
    session: AsyncSession, enrollment_id: uuid.UUID
) -> list[tuple[NodeProgress, LearningNode]]:
    rows = (
        await session.execute(
            select(NodeProgress, LearningNode)
            .join(LearningNode, LearningNode.id == NodeProgress.node_id)
            .where(NodeProgress.enrollment_id == enrollment_id)
            .order_by(LearningNode.created_at, LearningNode.title)
        )
    ).all()
    return [(row[0], row[1]) for row in rows]


async def graph_edges(
    session: AsyncSession, course_version_id: uuid.UUID
) -> list[NodeDependency]:
    node_ids = (
        (
            await session.execute(
                select(LearningNode.id).where(
                    LearningNode.course_version_id == course_version_id
                )
            )
        )
        .scalars()
        .all()
    )
    if not node_ids:
        return []
    return list(
        (
            await session.execute(
                select(NodeDependency).where(NodeDependency.source_node_id.in_(node_ids))
            )
        )
        .scalars()
        .all()
    )


# ── Progress / node completion ───────────────────────────────────────────────


def _mastery_threshold(node: LearningNode) -> float:
    rule = node.mastery_rule or {}
    for key in ("min_score", "threshold", "passing_score"):
        value = rule.get(key)
        if isinstance(value, int | float):
            return float(value)
    return DEFAULT_MASTERY_THRESHOLD


async def complete_node(
    session: AsyncSession, enrollment: Enrollment, node_id: uuid.UUID, *,
    score: float | None, time_spent_seconds: int, confidence: float | None,
) -> tuple[NodeProgress, list[uuid.UUID], bool]:
    progress = (
        await session.execute(
            select(NodeProgress).where(
                NodeProgress.enrollment_id == enrollment.id,
                NodeProgress.node_id == node_id,
            )
        )
    ).scalar_one_or_none()
    if progress is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Node is not part of this enrollment"
        )
    if progress.state == "locked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Node is locked; complete its prerequisites first",
        )

    node = await session.get(LearningNode, node_id)
    threshold = _mastery_threshold(node) if node is not None else DEFAULT_MASTERY_THRESHOLD
    has_explicit_rule = bool(node.mastery_rule) if node is not None else False

    progress.attempts += 1
    progress.time_spent_seconds += max(0, time_spent_seconds)
    if confidence is not None:
        progress.confidence = confidence
    if progress.completed_at is None:
        progress.completed_at = datetime.now(UTC)
    progress.state = "completed"

    mastered = await _evaluate_mastery(
        session,
        enrollment=enrollment,
        node_id=node_id,
        score=score,
        threshold=threshold,
        has_explicit_rule=has_explicit_rule,
    )
    if mastered:
        progress.state = "mastered"

    await session.flush()
    unlocked = await _unlock_nodes(session, enrollment)
    return progress, unlocked, mastered


async def _evaluate_mastery(
    session: AsyncSession, *, enrollment: Enrollment, node_id: uuid.UUID,
    score: float | None, threshold: float, has_explicit_rule: bool,
) -> bool:
    record = (
        await session.execute(
            select(MasteryRecord).where(
                MasteryRecord.enrollment_id == enrollment.id,
                MasteryRecord.node_id == node_id,
            )
        )
    ).scalar_one_or_none()

    if score is not None:
        meets = score >= threshold
        if record is None:
            record = MasteryRecord(
                enrollment_id=enrollment.id,
                node_id=node_id,
                score=score,
                status="mastered" if meets else "in_progress",
                evidence={"source": "node_completion"},
            )
            session.add(record)
        else:
            record.score = score
            record.status = "mastered" if meets else "in_progress"
        await session.flush()
        if meets:
            return True

    if record is not None and record.status == "mastered":
        return True
    if record is not None and record.score is not None and record.score >= threshold:
        return True
    # No explicit mastery bar -> completion implies mastery (avoids gate deadlocks).
    return not has_explicit_rule


async def _unlock_nodes(session: AsyncSession, enrollment: Enrollment) -> list[uuid.UUID]:
    rows = await node_progress_rows(session, enrollment.id)
    state_by_node = {node.id: prog.state for prog, node in rows}
    locked = [(prog, node) for prog, node in rows if prog.state == "locked"]
    if not locked:
        return []

    deps_by_target = await _incoming_locking_deps(
        session, [node.id for _, node in locked]
    )
    unlocked: list[uuid.UUID] = []
    for prog, node in locked:
        if _prereqs_met(deps_by_target.get(node.id, []), state_by_node):
            prog.state = "available"
            unlocked.append(node.id)
    if unlocked:
        await session.flush()
    return unlocked
