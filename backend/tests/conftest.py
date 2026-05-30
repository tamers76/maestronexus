"""Shared fixtures for projects + attendance tests.

These tests run against the configured (dev) Postgres. Each test builds a fully
isolated world (its own tenant, users, roles, course graph, class, enrollment)
with unique identifiers and tears everything down afterwards, so they never
collide with seeded data or each other.

Auth is exercised end-to-end via real JWTs (``create_access_token``); the API is
driven through ``httpx.ASGITransport`` against the in-process app.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal, engine
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.attendance.models import AttendanceRecord, AttendanceSession
from app.modules.courses.models import Course, CourseVersion, LearningNode
from app.modules.enrollment.models import Class, Enrollment
from app.modules.iam.models import (
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserRole,
)
from app.modules.projects.models import Feedback, Grade, Project, ProjectSubmission, Rubric

REQUIRED_PERMS = ["project.grade", "project.submit", "attendance.manage", "report.view_class"]


@dataclass
class World:
    tenant_id: uuid.UUID
    teacher_id: uuid.UUID
    learner_id: uuid.UUID
    other_teacher_id: uuid.UUID
    other_learner_id: uuid.UUID
    node_id: uuid.UUID
    course_version_id: uuid.UUID
    class_id: uuid.UUID
    other_class_id: uuid.UUID
    teacher_token: str
    learner_token: str
    other_teacher_token: str
    other_learner_token: str
    role_ids: list[uuid.UUID] = field(default_factory=list)
    course_id: uuid.UUID | None = None


@pytest_asyncio.fixture(autouse=True)
async def _dispose_global_engine():
    """Rebind the shared async engine per test.

    The app exposes a module-level ``engine`` whose asyncpg pool binds to the
    event loop that first used it. pytest-asyncio runs each test in a fresh
    function-scoped loop, so without this the second test onward hits
    "Event loop is closed". Disposing after each test (while its loop is still
    open) means the next test lazily creates a fresh pool in its own loop.
    """

    yield
    await engine.dispose()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _ensure_permissions(session) -> dict[str, Permission]:
    existing = {
        p.key: p
        for p in (
            await session.execute(select(Permission).where(Permission.key.in_(REQUIRED_PERMS)))
        ).scalars().all()
    }
    for key in REQUIRED_PERMS:
        if key not in existing:
            perm = Permission(key=key, description=f"test {key}")
            session.add(perm)
            await session.flush()
            existing[key] = perm
    return existing


async def _make_user(session, tenant_id, role_id, label) -> uuid.UUID:
    user = User(
        tenant_id=tenant_id,
        email=f"{label}-{uuid.uuid4().hex[:8]}@test.dev",
        display_name=label,
        password_hash=hash_password("x"),
        status="active",
        is_superuser=False,
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=role_id))
    return user.id


@pytest_asyncio.fixture
async def world() -> World:
    async with SessionLocal() as session:
        perms = await _ensure_permissions(session)

        tenant = Tenant(name="Test Tenant", slug=f"test-{uuid.uuid4().hex[:10]}")
        session.add(tenant)
        await session.flush()

        teacher_role = Role(tenant_id=tenant.id, key="t_teacher", name="Test Teacher")
        learner_role = Role(tenant_id=tenant.id, key="t_learner", name="Test Learner")
        session.add_all([teacher_role, learner_role])
        await session.flush()
        for key in ["project.grade", "attendance.manage", "report.view_class"]:
            session.add(
                RolePermission(role_id=teacher_role.id, permission_id=perms[key].id)
            )
        session.add(
            RolePermission(role_id=learner_role.id, permission_id=perms["project.submit"].id)
        )

        teacher_id = await _make_user(session, tenant.id, teacher_role.id, "teacher")
        learner_id = await _make_user(session, tenant.id, learner_role.id, "learner")
        other_teacher_id = await _make_user(session, tenant.id, teacher_role.id, "other-teacher")
        other_learner_id = await _make_user(session, tenant.id, learner_role.id, "other-learner")

        course = Course(tenant_id=tenant.id, title="Test Course", status="published")
        session.add(course)
        await session.flush()
        version = CourseVersion(course_id=course.id, version=1, state="published")
        session.add(version)
        await session.flush()
        node = LearningNode(course_version_id=version.id, type="project", title="Capstone")
        session.add(node)
        await session.flush()

        klass = Class(
            tenant_id=tenant.id, course_id=course.id, teacher_id=teacher_id, name="Class A"
        )
        other_class = Class(
            tenant_id=tenant.id,
            course_id=course.id,
            teacher_id=other_teacher_id,
            name="Class B",
        )
        session.add_all([klass, other_class])
        await session.flush()

        session.add(
            Enrollment(
                tenant_id=tenant.id,
                user_id=learner_id,
                class_id=klass.id,
                course_version_id=version.id,
                status="active",
            )
        )
        session.add(
            Enrollment(
                tenant_id=tenant.id,
                user_id=other_learner_id,
                class_id=other_class.id,
                course_version_id=version.id,
                status="active",
            )
        )
        await session.commit()

        w = World(
            tenant_id=tenant.id,
            teacher_id=teacher_id,
            learner_id=learner_id,
            other_teacher_id=other_teacher_id,
            other_learner_id=other_learner_id,
            node_id=node.id,
            course_version_id=version.id,
            class_id=klass.id,
            other_class_id=other_class.id,
            teacher_token=create_access_token(teacher_id, tenant.id),
            learner_token=create_access_token(learner_id, tenant.id),
            other_teacher_token=create_access_token(other_teacher_id, tenant.id),
            other_learner_token=create_access_token(other_learner_id, tenant.id),
            role_ids=[teacher_role.id, learner_role.id],
            course_id=course.id,
        )

    try:
        yield w
    finally:
        await _teardown(w)


async def _teardown(w: World) -> None:
    async with SessionLocal() as session:
        # Delete in FK-dependency order. Project-graph children first.
        proj_ids = (
            await session.execute(select(Project.id).where(Project.node_id == w.node_id))
        ).scalars().all()
        sub_ids = (
            await session.execute(
                select(ProjectSubmission.id).where(ProjectSubmission.project_id.in_(proj_ids))
            )
        ).scalars().all() if proj_ids else []
        grade_ids = (
            await session.execute(
                select(Grade.id).where(Grade.submission_id.in_(sub_ids))
            )
        ).scalars().all() if sub_ids else []

        if grade_ids:
            await session.execute(delete(Feedback).where(Feedback.grade_id.in_(grade_ids)))
            await session.execute(delete(Grade).where(Grade.id.in_(grade_ids)))
        if sub_ids:
            await session.execute(
                delete(ProjectSubmission).where(ProjectSubmission.id.in_(sub_ids))
            )
        if proj_ids:
            await session.execute(delete(Rubric).where(Rubric.project_id.in_(proj_ids)))
            await session.execute(delete(Project).where(Project.id.in_(proj_ids)))

        sess_ids = (
            await session.execute(
                select(AttendanceSession.id).where(AttendanceSession.tenant_id == w.tenant_id)
            )
        ).scalars().all()
        if sess_ids:
            await session.execute(
                delete(AttendanceRecord).where(AttendanceRecord.session_id.in_(sess_ids))
            )
            await session.execute(
                delete(AttendanceSession).where(AttendanceSession.id.in_(sess_ids))
            )

        await session.execute(delete(Enrollment).where(Enrollment.tenant_id == w.tenant_id))
        await session.execute(delete(Class).where(Class.tenant_id == w.tenant_id))
        await session.execute(delete(LearningNode).where(LearningNode.id == w.node_id))
        await session.execute(
            delete(CourseVersion).where(CourseVersion.id == w.course_version_id)
        )
        if w.course_id:
            await session.execute(delete(Course).where(Course.id == w.course_id))

        user_ids = [w.teacher_id, w.learner_id, w.other_teacher_id, w.other_learner_id]
        await session.execute(delete(UserRole).where(UserRole.user_id.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        if w.role_ids:
            await session.execute(
                delete(RolePermission).where(RolePermission.role_id.in_(w.role_ids))
            )
            await session.execute(delete(Role).where(Role.id.in_(w.role_ids)))
        await session.execute(delete(Tenant).where(Tenant.id == w.tenant_id))
        await session.commit()

    # Close pooled connections inside this test's event loop. The app + tests
    # share a module-level engine; on Windows asyncpg connections are bound to
    # the loop that created them, so we drain the pool before the loop closes.
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
