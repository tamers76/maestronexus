"""Attendance service: class-scoped session + record logic (docs/09).

Every read/write is scoped by tenant and by class ownership — a teacher only
touches sessions for classes they own (``Class.teacher_id``) or are assigned to
(``TeacherAssignment``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.deps import Principal
from app.modules.attendance.models import AttendanceRecord, AttendanceSession
from app.modules.attendance.schemas import RecordIn, SessionCreate
from app.modules.enrollment.models import Class, Enrollment
from app.modules.iam.models import TeacherAssignment, User


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


async def _teacher_class_ids(session: AsyncSession, user: Principal) -> set[uuid.UUID]:
    owned = (
        await session.execute(
            select(Class.id).where(Class.tenant_id == user.tenant_id, Class.teacher_id == user.id)
        )
    ).scalars().all()
    assigned = (
        await session.execute(
            select(TeacherAssignment.class_id)
            .join(Class, Class.id == TeacherAssignment.class_id)
            .where(Class.tenant_id == user.tenant_id, TeacherAssignment.user_id == user.id)
        )
    ).scalars().all()
    return set(owned) | set(assigned)


async def _require_class_access(
    session: AsyncSession, user: Principal, class_id: uuid.UUID
) -> Class:
    klass = await session.get(Class, class_id)
    if klass is None:
        raise _not_found("Class not found")
    if not user.is_superuser:
        if klass.tenant_id != user.tenant_id:
            raise _forbidden("Class belongs to another tenant")
        class_ids = await _teacher_class_ids(session, user)
        if class_id not in class_ids:
            raise _forbidden("You do not teach this class")
    return klass


async def list_classes(session: AsyncSession, user: Principal) -> list[Class]:
    """The caller's own classes — supports class selection in the UI."""

    if user.is_superuser:
        rows = (
            await session.execute(
                select(Class).where(Class.tenant_id == user.tenant_id).order_by(Class.name)
            )
        ).scalars().all()
        return list(rows)

    class_ids = await _teacher_class_ids(session, user)
    if not class_ids:
        return []
    rows = (
        await session.execute(
            select(Class).where(Class.id.in_(class_ids)).order_by(Class.name)
        )
    ).scalars().all()
    return list(rows)


# ── Sessions ─────────────────────────────────────────────────────────────────


async def create_session(
    session: AsyncSession, user: Principal, data: SessionCreate
) -> AttendanceSession:
    klass = await _require_class_access(session, user, data.class_id)
    obj = AttendanceSession(
        tenant_id=klass.tenant_id,
        class_id=data.class_id,
        scheduled_at=data.scheduled_at,
        mode=data.mode,
    )
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        tenant_id=klass.tenant_id,
        actor_id=user.id,
        action="attendance.session.create",
        object_type="attendance_session",
        object_id=obj.id,
        metadata={"class_id": str(data.class_id)},
    )
    await session.commit()
    await session.refresh(obj)
    return obj


async def list_sessions(
    session: AsyncSession,
    user: Principal,
    *,
    class_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[AttendanceSession], int]:
    base = select(AttendanceSession).where(AttendanceSession.tenant_id == user.tenant_id)
    if not user.is_superuser:
        class_ids = await _teacher_class_ids(session, user)
        if not class_ids:
            return [], 0
        base = base.where(AttendanceSession.class_id.in_(class_ids))
    if class_id is not None:
        base = base.where(AttendanceSession.class_id == class_id)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    items = (
        (
            await session.execute(
                base.order_by(AttendanceSession.scheduled_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(items), total


async def get_session(
    session: AsyncSession, user: Principal, session_id: uuid.UUID
) -> AttendanceSession:
    obj = await session.get(AttendanceSession, session_id)
    if obj is None:
        raise _not_found("Attendance session not found")
    await _require_class_access(session, user, obj.class_id)
    return obj


# ── Roster + records ─────────────────────────────────────────────────────────


async def session_roster(
    session: AsyncSession, user: Principal, session_id: uuid.UUID
) -> list[dict]:
    """Class roster merged with any existing marks for the session."""

    obj = await get_session(session, user, session_id)

    learners = (
        await session.execute(
            select(User.id, User.display_name, User.email)
            .join(Enrollment, Enrollment.user_id == User.id)
            .where(Enrollment.class_id == obj.class_id, Enrollment.deleted_at.is_(None))
            .order_by(User.display_name)
        )
    ).all()

    records = (
        await session.execute(
            select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
        )
    ).scalars().all()
    by_learner = {r.learner_id: r for r in records}

    roster = []
    for learner_id, display_name, email in learners:
        rec = by_learner.get(learner_id)
        roster.append(
            {
                "learner_id": learner_id,
                "display_name": display_name,
                "email": email,
                "status": rec.status if rec else None,
                "marked_at": rec.marked_at if rec else None,
            }
        )
    return roster


async def list_records(
    session: AsyncSession, user: Principal, session_id: uuid.UUID
) -> list[AttendanceRecord]:
    await get_session(session, user, session_id)
    rows = (
        await session.execute(
            select(AttendanceRecord)
            .where(AttendanceRecord.session_id == session_id)
            .order_by(AttendanceRecord.created_at)
        )
    ).scalars().all()
    return list(rows)


async def mark_records(
    session: AsyncSession,
    user: Principal,
    session_id: uuid.UUID,
    records: list[RecordIn],
) -> list[AttendanceRecord]:
    """Upsert one record per learner for the session (present/absent/late/excused)."""

    obj = await get_session(session, user, session_id)

    enrolled = set(
        (
            await session.execute(
                select(Enrollment.user_id).where(
                    Enrollment.class_id == obj.class_id, Enrollment.deleted_at.is_(None)
                )
            )
        ).scalars().all()
    )

    existing = {
        r.learner_id: r
        for r in (
            await session.execute(
                select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
            )
        ).scalars().all()
    }

    now = datetime.now(UTC)
    for item in records:
        if item.learner_id not in enrolled:
            raise _forbidden("Learner is not enrolled in this class")
        rec = existing.get(item.learner_id)
        if rec is None:
            rec = AttendanceRecord(
                session_id=session_id,
                learner_id=item.learner_id,
                status=item.status,
                marked_at=now,
                marked_by=user.id,
            )
            session.add(rec)
            existing[item.learner_id] = rec
        else:
            rec.status = item.status
            rec.marked_at = now
            rec.marked_by = user.id

    await record_audit(
        session,
        tenant_id=obj.tenant_id,
        actor_id=user.id,
        action="attendance.mark",
        object_type="attendance_session",
        object_id=session_id,
        metadata={"count": len(records)},
    )
    await session.commit()

    return await list_records(session, user, session_id)
