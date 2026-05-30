"""Rule-based adaptive engine (docs/05).

Pure-ish decision function over (graph, progress, signals, overrides) producing a
``Recommendation``. Precedence (docs/05):
  1. Teacher override wins.
  2. Remediation when a recent attempt scored below the mastery threshold.
  3. Otherwise the next ``available`` (unlocked, incomplete) node in graph order.
  4. Nothing left -> course complete.
Every recommendation carries a human-readable ``reason``.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.adaptive.models import Recommendation
from app.modules.courses.models import LearningNode
from app.modules.enrollment import service as enrollment_service
from app.modules.enrollment.models import Enrollment, MasteryRecord, NodeProgress
from app.modules.enrollment.service import DEFAULT_MASTERY_THRESHOLD

_COMPLETED_STATES = ("completed", "mastered")
# Node types that count as remediation/practice when concepts are weak.
_REMEDIATION_TYPES = {"remediation", "practice", "review", "alternative"}


@dataclass
class NextNode:
    recommendation_id: object | None
    node_id: object | None
    node_title: str | None
    node_type: str | None
    reason: str
    source: str | None
    course_complete: bool


async def _active_override(
    session: AsyncSession, enrollment: Enrollment
) -> tuple[Recommendation, LearningNode] | None:
    """Most recent teacher override whose target node is not yet completed."""
    rec = (
        await session.execute(
            select(Recommendation)
            .where(
                Recommendation.enrollment_id == enrollment.id,
                Recommendation.source == "teacher_override",
            )
            .order_by(Recommendation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if rec is None:
        return None

    progress = (
        await session.execute(
            select(NodeProgress).where(
                NodeProgress.enrollment_id == enrollment.id,
                NodeProgress.node_id == rec.recommended_node_id,
            )
        )
    ).scalar_one_or_none()
    if progress is not None and progress.state in _COMPLETED_STATES:
        return None  # already done; fall back to the engine
    node = await session.get(LearningNode, rec.recommended_node_id)
    if node is None:
        return None
    return rec, node


async def _has_weak_attempt(
    session: AsyncSession, enrollment: Enrollment, threshold: float
) -> bool:
    record = (
        await session.execute(
            select(MasteryRecord).where(
                MasteryRecord.enrollment_id == enrollment.id,
                MasteryRecord.status != "mastered",
                MasteryRecord.score.is_not(None),
                MasteryRecord.score < threshold,
            )
        )
    ).first()
    return record is not None


async def compute_next_node(session: AsyncSession, enrollment: Enrollment) -> NextNode:
    # 1. Teacher override wins.
    override = await _active_override(session, enrollment)
    if override is not None:
        rec, node = override
        return NextNode(
            recommendation_id=rec.id,
            node_id=node.id,
            node_title=node.title,
            node_type=node.type,
            reason=rec.reason or "Assigned by your teacher",
            source="teacher_override",
            course_complete=False,
        )

    rows = await enrollment_service.node_progress_rows(session, enrollment.id)
    total = len(rows)
    completed = sum(1 for prog, _ in rows if prog.state in _COMPLETED_STATES)
    available = [(prog, node) for prog, node in rows if prog.state == "available"]

    # 4. Nothing available.
    if not available:
        course_complete = total > 0 and completed == total
        if course_complete:
            reason = "Course complete — you've finished every node. Great work!"
        elif total == 0:
            reason = "This course has no nodes yet."
        else:
            reason = "No nodes are available right now; complete prerequisites to unlock more."
        return NextNode(None, None, None, None, reason, None, course_complete=course_complete)

    # 2. Prefer remediation when a recent attempt scored low.
    if await _has_weak_attempt(session, enrollment, DEFAULT_MASTERY_THRESHOLD):
        remediation = next(
            ((prog, node) for prog, node in available if node.type in _REMEDIATION_TYPES),
            None,
        )
        if remediation is not None:
            _, node = remediation
            reason = (
                f"Strengthen weak concepts before moving on — start “{node.title}”."
            )
            rec = await _persist(session, enrollment, node, reason)
            return NextNode(rec.id, node.id, node.title, node.type, reason, "engine", False)

    # 3. Next available node in graph order.
    _, node = available[0]
    if completed == 0:
        reason = f"Start here: “{node.title}”."
    else:
        reason = f"Continue your path: “{node.title}”."
    rec = await _persist(session, enrollment, node, reason)
    return NextNode(rec.id, node.id, node.title, node.type, reason, "engine", False)


async def _persist(
    session: AsyncSession, enrollment: Enrollment, node: LearningNode, reason: str
) -> Recommendation:
    rec = Recommendation(
        enrollment_id=enrollment.id,
        recommended_node_id=node.id,
        reason=reason,
        source="engine",
    )
    session.add(rec)
    await session.flush()
    return rec


async def create_override(
    session: AsyncSession, enrollment: Enrollment, node_id, reason: str | None
) -> tuple[Recommendation, LearningNode]:
    """Persist a teacher override recommendation; the GET will return it (override wins)."""
    progress = (
        await session.execute(
            select(NodeProgress).where(
                NodeProgress.enrollment_id == enrollment.id,
                NodeProgress.node_id == node_id,
            )
        )
    ).scalar_one_or_none()
    node = await session.get(LearningNode, node_id)
    if progress is None or node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node is not part of this enrollment's course version",
        )
    rec = Recommendation(
        enrollment_id=enrollment.id,
        recommended_node_id=node_id,
        reason=reason or "Assigned by your teacher",
        source="teacher_override",
    )
    session.add(rec)
    await session.flush()
    return rec, node
