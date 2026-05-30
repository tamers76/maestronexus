"""Analytics service: read-only, tenant-scoped aggregates (docs/09).

All queries filter by ``tenant_id`` and never mutate state. Cross-module data is
read via the platform's shared model classes; these functions are the read
interface callers should use rather than duplicating the SQL.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.schemas import (
    ClassReport,
    ClassSummary,
    DashboardEngagement,
    DashboardTotals,
    InstitutionDashboard,
    RoleCount,
)
from app.modules.attendance.models import AttendanceRecord, AttendanceSession
from app.modules.courses.models import Course
from app.modules.enrollment.models import Class, Enrollment, NodeProgress
from app.modules.iam.models import Role, TeacherAssignment, User, UserRole

# Node states that count as "completed" for progress aggregates.
_COMPLETED_STATES = ("completed", "mastered")
# Attendance statuses that count as attended.
_ATTENDED_STATES = ("present", "late")


def _pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator * 100, 1)


async def _completion_counts(session: AsyncSession, enrollment_ids: Select) -> tuple[int, int]:
    """Return ``(completed_nodes, total_nodes)`` for the given enrollment id subquery."""

    completed = func.count(case((NodeProgress.state.in_(_COMPLETED_STATES), 1), else_=None))
    row = (
        await session.execute(
            select(completed, func.count(NodeProgress.id)).where(
                NodeProgress.enrollment_id.in_(enrollment_ids)
            )
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


async def _attendance_counts(session: AsyncSession, session_ids: Select) -> tuple[int, int]:
    """Return ``(attended, total)`` records for the given attendance-session subquery."""

    attended = func.count(case((AttendanceRecord.status.in_(_ATTENDED_STATES), 1), else_=None))
    row = (
        await session.execute(
            select(attended, func.count(AttendanceRecord.id)).where(
                AttendanceRecord.session_id.in_(session_ids)
            )
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


async def get_class(
    session: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID
) -> Class | None:
    return (
        await session.execute(
            select(Class).where(Class.id == class_id, Class.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()


async def user_can_view_class(session: AsyncSession, user_id: uuid.UUID, cls: Class) -> bool:
    """Object-level scope: the teacher who owns the class, or an assigned TA/teacher."""

    if cls.teacher_id == user_id:
        return True
    found = (
        await session.execute(
            select(TeacherAssignment.id).where(
                TeacherAssignment.user_id == user_id,
                TeacherAssignment.class_id == cls.id,
            )
        )
    ).scalar_one_or_none()
    return found is not None


async def list_classes(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    restrict_to_user: uuid.UUID | None = None,
    limit: int = 200,
) -> list[ClassSummary]:
    """List classes with enrollment counts for reporting.

    When ``restrict_to_user`` is set, only classes that user owns or is assigned
    to are returned (own-class scope for teachers).
    """

    enroll_count = func.count(Enrollment.id.distinct())
    stmt = (
        select(Class, Course.title, enroll_count)
        .outerjoin(Course, Course.id == Class.course_id)
        .outerjoin(
            Enrollment,
            (Enrollment.class_id == Class.id) & (Enrollment.deleted_at.is_(None)),
        )
        .where(Class.tenant_id == tenant_id)
        .group_by(Class.id, Course.title)
        .order_by(enroll_count.desc(), Class.name)
        .limit(limit)
    )
    if restrict_to_user is not None:
        assigned = select(TeacherAssignment.class_id).where(
            TeacherAssignment.user_id == restrict_to_user
        )
        stmt = stmt.where((Class.teacher_id == restrict_to_user) | (Class.id.in_(assigned)))

    rows = (await session.execute(stmt)).all()
    return [
        ClassSummary(
            class_id=cls.id,
            name=cls.name,
            course_title=title,
            teacher_id=cls.teacher_id,
            enrollment_count=int(count or 0),
        )
        for cls, title, count in rows
    ]


async def get_class_report(
    session: AsyncSession, tenant_id: uuid.UUID, cls: Class
) -> ClassReport:
    course_title = (
        await session.execute(select(Course.title).where(Course.id == cls.course_id))
    ).scalar_one_or_none()

    total_enroll = (
        await session.execute(
            select(func.count(Enrollment.id)).where(
                Enrollment.class_id == cls.id, Enrollment.deleted_at.is_(None)
            )
        )
    ).scalar_one()
    active_enroll = (
        await session.execute(
            select(func.count(Enrollment.id)).where(
                Enrollment.class_id == cls.id,
                Enrollment.deleted_at.is_(None),
                Enrollment.status == "active",
            )
        )
    ).scalar_one()

    enrollment_ids = select(Enrollment.id).where(
        Enrollment.class_id == cls.id, Enrollment.deleted_at.is_(None)
    )
    completed_nodes, total_nodes = await _completion_counts(session, enrollment_ids)

    session_ids = select(AttendanceSession.id).where(AttendanceSession.class_id == cls.id)
    attended, total_records = await _attendance_counts(session, session_ids)

    return ClassReport(
        class_id=cls.id,
        name=cls.name,
        course_title=course_title,
        teacher_id=cls.teacher_id,
        enrollment_count=int(total_enroll),
        active_enrollment_count=int(active_enroll),
        total_nodes=total_nodes,
        completed_nodes=completed_nodes,
        avg_completion_pct=_pct(completed_nodes, total_nodes),
        attendance_records=total_records,
        attendance_rate=_pct(attended, total_records),
    )


async def get_institution_dashboard(
    session: AsyncSession, tenant_id: uuid.UUID
) -> InstitutionDashboard:
    users = (
        await session.execute(
            select(func.count(User.id)).where(
                User.tenant_id == tenant_id, User.deleted_at.is_(None)
            )
        )
    ).scalar_one()
    courses = (
        await session.execute(
            select(func.count(Course.id)).where(Course.tenant_id == tenant_id)
        )
    ).scalar_one()
    classes = (
        await session.execute(
            select(func.count(Class.id)).where(Class.tenant_id == tenant_id)
        )
    ).scalar_one()
    enrollments = (
        await session.execute(
            select(func.count(Enrollment.id)).where(
                Enrollment.tenant_id == tenant_id, Enrollment.deleted_at.is_(None)
            )
        )
    ).scalar_one()
    active_enrollments = (
        await session.execute(
            select(func.count(Enrollment.id)).where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.deleted_at.is_(None),
                Enrollment.status == "active",
            )
        )
    ).scalar_one()

    tenant_enrollment_ids = select(Enrollment.id).where(
        Enrollment.tenant_id == tenant_id, Enrollment.deleted_at.is_(None)
    )
    completed_nodes, total_nodes = await _completion_counts(session, tenant_enrollment_ids)

    tenant_session_ids = select(AttendanceSession.id).where(
        AttendanceSession.tenant_id == tenant_id
    )
    attended, total_records = await _attendance_counts(session, tenant_session_ids)

    top_classes = await list_classes(session, tenant_id, limit=5)

    role_count = func.count(UserRole.user_id.distinct())
    role_rows = (
        await session.execute(
            select(Role.key, role_count)
            .join(UserRole, UserRole.role_id == Role.id)
            .join(User, User.id == UserRole.user_id)
            .where(
                Role.tenant_id == tenant_id,
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
            .group_by(Role.key)
            .order_by(role_count.desc())
        )
    ).all()

    return InstitutionDashboard(
        totals=DashboardTotals(
            users=int(users),
            courses=int(courses),
            classes=int(classes),
            enrollments=int(enrollments),
        ),
        engagement=DashboardEngagement(
            active_enrollments=int(active_enrollments),
            avg_completion_pct=_pct(completed_nodes, total_nodes),
            attendance_rate=_pct(attended, total_records),
        ),
        top_classes=top_classes,
        users_by_role=[RoleCount(role=key, count=int(count)) for key, count in role_rows],
    )
