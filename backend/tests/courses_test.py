"""Integration tests for the Courses & Learning Graph module (docs/04, docs/15).

Exercises the MVP acceptance criterion end-to-end against the dev database:
a designer creates a course, adds nodes, draws ``requires`` / ``mastery_gate``
dependencies (cycles rejected), and publishes a version. Also asserts RBAC.

Runs the ASGI app in-process (no live server / no port binding) and cleans up
every row it creates.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.modules.courses.models import Course
from app.modules.iam.models import AuditLog

BASE = "http://test"
API = "/api/v1"
PASSWORD = "pass"


async def _login(client: AsyncClient, email: str) -> str:
    res = await client.post(
        f"{API}/iam/auth/login", json={"username": email, "password": PASSWORD}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture
async def sessionmaker():
    # A fresh engine per test keeps the asyncpg pool bound to the active event
    # loop (pytest-asyncio uses a new loop per test, esp. on Windows/Proactor).
    engine = create_async_engine(settings.database_url)
    maker = async_sessionmaker(bind=engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest.fixture
async def client(sessionmaker) -> AsyncIterator[AsyncClient]:
    async def _override_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c
    app.dependency_overrides.pop(get_session, None)


async def _cleanup(
    sessionmaker, course_id: uuid.UUID, object_ids: list[uuid.UUID]
) -> None:
    async with sessionmaker() as session:
        # Course delete cascades versions -> nodes -> dependencies.
        await session.execute(delete(Course).where(Course.id == course_id))
        if object_ids:
            await session.execute(
                delete(AuditLog).where(AuditLog.object_id.in_(object_ids))
            )
        await session.commit()


async def test_designer_builds_and_publishes_graph(client: AsyncClient, sessionmaker):
    token = await _login(client, "designer")
    auth = {"Authorization": f"Bearer {token}"}

    created_ids: list[uuid.UUID] = []
    course_id: uuid.UUID | None = None
    try:
        # 1. Create a course.
        res = await client.post(
            f"{API}/courses",
            headers=auth,
            json={"title": "Test Algebra", "description": "pytest course"},
        )
        assert res.status_code == 201, res.text
        course = res.json()
        course_id = uuid.UUID(course["id"])
        created_ids.append(course_id)
        assert course["status"] == "draft"

        # It shows up in the paginated list.
        res = await client.get(f"{API}/courses?limit=200", headers=auth)
        assert res.status_code == 200
        listing = res.json()
        assert any(c["id"] == course["id"] for c in listing["items"])
        assert listing["total"] >= 1

        # 2. Create a version.
        res = await client.post(
            f"{API}/courses/{course['id']}/versions",
            headers=auth,
            json={"clone_from_latest": False},
        )
        assert res.status_code == 201, res.text
        version = res.json()
        version_id = version["id"]
        created_ids.append(uuid.UUID(version_id))
        assert version["version"] == 1
        assert version["state"] == "draft"

        # 3. Add three nodes.
        node_ids = []
        for i, title in enumerate(["Intro", "Variables", "Mastery Check"]):
            res = await client.post(
                f"{API}/courses/versions/{version_id}/nodes",
                headers=auth,
                json={
                    "title": title,
                    "type": "lesson" if i < 2 else "mastery_checkpoint",
                    "position": {"x": i * 100, "y": 0},
                },
            )
            assert res.status_code == 201, res.text
            node = res.json()
            node_ids.append(node["id"])
            created_ids.append(uuid.UUID(node["id"]))
            # Position persisted in node_metadata.
            assert node["position"]["x"] == i * 100

        n_intro, n_vars, n_check = node_ids

        # 4. Draw a `requires` edge (Intro -> Variables).
        res = await client.post(
            f"{API}/courses/versions/{version_id}/dependencies",
            headers=auth,
            json={
                "source_node_id": n_intro,
                "target_node_id": n_vars,
                "dependency_type": "requires",
            },
        )
        assert res.status_code == 201, res.text
        created_ids.append(uuid.UUID(res.json()["id"]))

        # ... and a `mastery_gate` edge (Variables -> Mastery Check).
        res = await client.post(
            f"{API}/courses/versions/{version_id}/dependencies",
            headers=auth,
            json={
                "source_node_id": n_vars,
                "target_node_id": n_check,
                "dependency_type": "mastery_gate",
            },
        )
        assert res.status_code == 201, res.text
        gate_id = res.json()["id"]
        created_ids.append(uuid.UUID(gate_id))

        # 5. A back-edge that would form a cycle is rejected (400).
        res = await client.post(
            f"{API}/courses/versions/{version_id}/dependencies",
            headers=auth,
            json={
                "source_node_id": n_check,
                "target_node_id": n_intro,
                "dependency_type": "requires",
            },
        )
        assert res.status_code == 400, res.text
        assert "cycle" in res.text.lower()

        # 6. Graph projection is React-Flow shaped.
        res = await client.get(
            f"{API}/courses/versions/{version_id}/graph", headers=auth
        )
        assert res.status_code == 200, res.text
        graph = res.json()
        assert len(graph["nodes"]) == 3
        assert len(graph["edges"]) == 2
        assert {e["data"]["dependencyType"] for e in graph["edges"]} == {
            "requires",
            "mastery_gate",
        }
        assert graph["nodes"][0]["data"]["label"]

        # Deleting an edge works.
        res = await client.delete(
            f"{API}/courses/dependencies/{gate_id}", headers=auth
        )
        assert res.status_code == 200, res.text

        # 7. Publish the version.
        res = await client.post(
            f"{API}/courses/versions/{version_id}/publish", headers=auth
        )
        assert res.status_code == 200, res.text
        published = res.json()
        assert published["state"] == "published"
        assert published["published_at"] is not None

        # Published versions are read-only: node creation now conflicts.
        res = await client.post(
            f"{API}/courses/versions/{version_id}/nodes",
            headers=auth,
            json={"title": "Too late"},
        )
        assert res.status_code == 409, res.text
    finally:
        if course_id is not None:
            await _cleanup(sessionmaker, course_id, created_ids)


async def test_learner_cannot_manage_courses(client: AsyncClient):
    token = await _login(client, "learner")
    auth = {"Authorization": f"Bearer {token}"}
    res = await client.post(
        f"{API}/courses", headers=auth, json={"title": "nope"}
    )
    assert res.status_code == 403, res.text


async def test_requires_authentication(client: AsyncClient):
    res = await client.get(f"{API}/courses")
    assert res.status_code == 401, res.text
