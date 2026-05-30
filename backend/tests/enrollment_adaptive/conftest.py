"""Fixtures for the enrollment + adaptive tests.

Lives in its own subpackage so its richer ``world`` (a 3-node graph: n1, n2
requires n1, n3 mastery-gated behind n2) does not collide with the projects/
attendance ``world`` in ``tests/conftest.py``. The autouse engine-dispose
fixture from the parent conftest still applies here.

Edge direction matches the enrollment service: for ``requires``/``mastery_gate``
the *target* is locked until the *source* is completed/mastered.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.courses.models import (
    Course,
    CourseVersion,
    LearningNode,
    NodeDependency,
)
from app.modules.enrollment.models import Class, Enrollment
from app.modules.iam.models import (
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserRole,
)

TEACHER_PERMS = ["class.manage", "node.assign", "report.view_class"]
LEARNER_PERMS = ["node.progress"]
ALL_PERMS = TEACHER_PERMS + LEARNER_PERMS


@dataclass
class World:
    tenant_id: uuid.UUID
    course_id: uuid.UUID
    version_id: uuid.UUID
    teacher_id: uuid.UUID
    learner_id: uuid.UUID
    learner_email: str
    teacher_token: str
    learner_token: str
    node_ids: dict[str, uuid.UUID]
    role_ids: list[uuid.UUID] = field(default_factory=list)


async def _ensure_permissions(session) -> dict[str, Permission]:
    existing = {
        p.key: p
        for p in (
            await session.execute(select(Permission).where(Permission.key.in_(ALL_PERMS)))
        ).scalars().all()
    }
    for key in ALL_PERMS:
        if key not in existing:
            perm = Permission(key=key, description=f"test {key}")
            session.add(perm)
            await session.flush()
            existing[key] = perm
    return existing


@pytest_asyncio.fixture
async def world():
    async with SessionLocal() as session:
        perms = await _ensure_permissions(session)

        tenant = Tenant(name="Enroll Test", slug=f"enr-{uuid.uuid4().hex[:10]}")
        session.add(tenant)
        await session.flush()

        teacher_role = Role(tenant_id=tenant.id, key="t_teacher", name="Test Teacher")
        learner_role = Role(tenant_id=tenant.id, key="t_learner", name="Test Learner")
        session.add_all([teacher_role, learner_role])
        await session.flush()
        for key in TEACHER_PERMS:
            session.add(RolePermission(role_id=teacher_role.id, permission_id=perms[key].id))
        for key in LEARNER_PERMS:
            session.add(RolePermission(role_id=learner_role.id, permission_id=perms[key].id))

        teacher = User(
            tenant_id=tenant.id,
            email=f"teacher-{uuid.uuid4().hex[:8]}@test.dev",
            display_name="Teacher",
            password_hash=hash_password("x"),
        )
        learner = User(
            tenant_id=tenant.id,
            email=f"learner-{uuid.uuid4().hex[:8]}@test.dev",
            display_name="Learner",
            password_hash=hash_password("x"),
        )
        session.add_all([teacher, learner])
        await session.flush()
        session.add(UserRole(user_id=teacher.id, role_id=teacher_role.id))
        session.add(UserRole(user_id=learner.id, role_id=learner_role.id))

        course = Course(tenant_id=tenant.id, title="Test Course", status="published")
        session.add(course)
        await session.flush()
        version = CourseVersion(course_id=course.id, version=1, state="published")
        session.add(version)
        await session.flush()

        n1 = LearningNode(course_version_id=version.id, type="lesson", title="1. Intro")
        n2 = LearningNode(course_version_id=version.id, type="lesson", title="2. Basics")
        n3 = LearningNode(course_version_id=version.id, type="lesson", title="3. Advanced")
        session.add_all([n1, n2, n3])
        await session.flush()

        # target is locked until source is completed/mastered.
        session.add(
            NodeDependency(source_node_id=n1.id, target_node_id=n2.id, dependency_type="requires")
        )
        session.add(
            NodeDependency(
                source_node_id=n2.id, target_node_id=n3.id, dependency_type="mastery_gate"
            )
        )
        await session.commit()

        w = World(
            tenant_id=tenant.id,
            course_id=course.id,
            version_id=version.id,
            teacher_id=teacher.id,
            learner_id=learner.id,
            learner_email=learner.email,
            teacher_token=create_access_token(teacher.id, tenant.id),
            learner_token=create_access_token(learner.id, tenant.id),
            node_ids={"n1": n1.id, "n2": n2.id, "n3": n3.id},
            role_ids=[teacher_role.id, learner_role.id],
        )

    try:
        yield w
    finally:
        await _teardown(w)


async def _teardown(w: World) -> None:
    async with SessionLocal() as session:
        # Enrollments cascade to node_progress + recommendations.
        await session.execute(delete(Enrollment).where(Enrollment.tenant_id == w.tenant_id))
        await session.execute(delete(Class).where(Class.tenant_id == w.tenant_id))
        node_ids = list(w.node_ids.values())
        await session.execute(
            delete(NodeDependency).where(NodeDependency.source_node_id.in_(node_ids))
        )
        await session.execute(delete(LearningNode).where(LearningNode.id.in_(node_ids)))
        await session.execute(delete(CourseVersion).where(CourseVersion.id == w.version_id))
        await session.execute(delete(Course).where(Course.id == w.course_id))
        user_ids = [w.teacher_id, w.learner_id]
        await session.execute(delete(UserRole).where(UserRole.user_id.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.execute(
            delete(RolePermission).where(RolePermission.role_id.in_(w.role_ids))
        )
        await session.execute(delete(Role).where(Role.id.in_(w.role_ids)))
        await session.execute(delete(Tenant).where(Tenant.id == w.tenant_id))
        await session.commit()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
