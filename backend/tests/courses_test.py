"""Integration tests for the Courses & Learning Graph module (docs/04, docs/15).

Exercises the MVP acceptance criterion end-to-end against the dev database:
a designer creates a course, adds nodes, draws ``requires`` / ``mastery_gate``
dependencies (cycles rejected), and publishes a version. Also asserts RBAC.

Runs the ASGI app in-process (no live server / no port binding) and cleans up
every row it creates.
"""

from __future__ import annotations

import base64
import re
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import SessionLocal, get_session
from app.main import app
from app.modules.courses.models import Course
from app.modules.iam.models import AuditLog
from app.modules.stages.models import StageRun

BASE = "http://test"
API = "/api/v1"
PASSWORD = "pass"


def _canon_clo_code(code: str) -> str:
    """Normalize a CLO code for comparison (``CLO1`` and ``CLO-1`` are equal).

    The offline deterministic syllabus extractor renumbers outcomes to the
    canonical ``CLO-1`` form, whereas a live LLM may echo the syllabus' own
    ``CLO1`` spelling. Both are valid identifiers (downstream CLO matching falls
    back to position), so tests compare on a punctuation-insensitive form.
    """

    return re.sub(r"[^a-z0-9]", "", (code or "").lower())


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


async def _cleanup_clo_course(course_id: uuid.UUID) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(StageRun).where(StageRun.course_id == course_id))
        # learning_outcomes cascade on course delete; Course cascade covers versions.
        await session.execute(delete(Course).where(Course.id == course_id))
        await session.commit()


async def test_create_course_from_form_extracts_clos(client: AsyncClient):
    token = await _login(client, "designer")
    auth = {"Authorization": f"Bearer {token}"}

    course_id: uuid.UUID | None = None
    try:
        res = await client.post(
            f"{API}/courses/from-form",
            headers=auth,
            json={
                "title": "Curriculum Design",
                "description": "manual entry test",
                "course_code": "MDLD602",
                "credit_hours": 3,
                "clos": [
                    "Evaluate strengths and limitations of a curriculum framework",
                    "Design an adaptive learning sequence",
                    "   ",
                ],
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        course_id = uuid.UUID(body["course"]["id"])
        assert body["course"]["course_code"] == "MDLD602"
        assert body["course"]["credit_hours"] == 3
        # Blank CLO is dropped; codes are auto-assigned.
        assert len(body["clos"]) == 2
        assert {c["code"] for c in body["clos"]} == {"CLO-1", "CLO-2"}

        res = await client.get(f"{API}/courses/{course_id}/clos", headers=auth)
        assert res.status_code == 200, res.text
        clos = res.json()
        assert len(clos["clos"]) == 2
        assert clos["clos"][0]["position"] == 0
    finally:
        if course_id is not None:
            await _cleanup_clo_course(course_id)


async def test_create_course_from_syllabus_extracts_clos(client: AsyncClient):
    """Uploading a syllabus whose text contains CLOs yields extracted CLO rows.

    Reproduces the original bug (offline intake stage returned no ``clos`` so no
    rows were written) and proves the DeepT Stage-1 fallback now recovers them.
    """

    token = await _login(client, "designer")
    auth = {"Authorization": f"Bearer {token}"}

    syllabus = (
        "Course Title: Introduction to Data Science\n"
        "Course Code: DS 101\n"
        "Credit Hours: 3\n\n"
        "Course Description:\n"
        "An introductory survey of data science methods.\n\n"
        "Course Learning Outcomes (CLOs):\n"
        "CLO1: Explain the fundamental concepts of data science and its applications.\n"
        "CLO2: Apply statistical methods to analyze real-world datasets.\n"
        "CLO3: Evaluate the effectiveness of machine learning models for a problem.\n\n"
        "Weekly Plan:\n"
        "Week 1: Introduction to the field\n"
        "Week 2: Probability and statistics review\n"
    )
    content_b64 = base64.b64encode(syllabus.encode("utf-8")).decode("ascii")

    course_id: uuid.UUID | None = None
    try:
        res = await client.post(
            f"{API}/courses/from-syllabus",
            headers=auth,
            json={
                "filename": "ds101_syllabus.txt",
                "mime_type": "text/plain",
                "content_base64": content_b64,
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        course_id = uuid.UUID(body["course"]["id"])

        # CLOs are extracted verbatim from the syllabus even with the offline stub.
        statements = [c["statement"] for c in body["clos"]]
        assert len(statements) == 3, statements
        assert statements[0].startswith("Explain the fundamental concepts")
        # Codes are sequential CLO identifiers; tolerate live-LLM ``CLO1`` and
        # offline ``CLO-1`` spellings without weakening the extraction coverage.
        assert {_canon_clo_code(c["code"]) for c in body["clos"]} == {
            "clo1",
            "clo2",
            "clo3",
        }

        # Course metadata is recovered from the document too.
        assert body["course"]["title"] == "Introduction to Data Science"
        assert body["course"]["course_code"] == "DS 101"
        assert body["course"]["credit_hours"] == 3

        # And the rows persist / are listable in order.
        res = await client.get(f"{API}/courses/{course_id}/clos", headers=auth)
        assert res.status_code == 200, res.text
        clos = res.json()["clos"]
        assert len(clos) == 3
        assert clos[0]["position"] == 0
    finally:
        if course_id is not None:
            await _cleanup_clo_course(course_id)


async def test_clo_refinement_promotes_on_sme_approval(client: AsyncClient):
    designer = await _login(client, "designer")
    admin = await _login(client, "admin")

    course_id: uuid.UUID | None = None
    try:
        res = await client.post(
            f"{API}/courses/from-form",
            headers={"Authorization": f"Bearer {designer}"},
            json={"title": "Refine Me", "clos": ["Explain the water cycle"]},
        )
        assert res.status_code == 201, res.text
        course_id = uuid.UUID(res.json()["course"]["id"])

        # Seed a succeeded CLO Refinement run with a structured artifact (the
        # offline LLM stub can't emit valid JSON, so craft it directly).
        async with SessionLocal() as session:
            course = await session.get(Course, course_id)
            run = StageRun(
                tenant_id=course.tenant_id,
                created_by=course.created_by,
                course_id=course_id,
                stage_key="clo_refinement",
                status="succeeded",
                execution_mode="single",
                input_refs={},
                output={
                    "text": "{}",
                    "artifact": {
                        "clos": [
                            {
                                "code": "CLO-1",
                                "original_statement": "Explain the water cycle",
                                "statement": (
                                    "Analyze the stages of the water cycle using "
                                    "evidence-based criteria"
                                ),
                                "bloom_level": "Analyze",
                                "measurable": True,
                                "evidence_of_mastery": "Annotated diagram with justification",
                            }
                        ]
                    },
                    "gaps": [],
                    "stubbed": True,
                    "output_kind": "refined_clos",
                },
                council_transcript={},
                risk_score=0.3,
                review_status="needs_review",
            )
            session.add(run)
            await session.commit()
            run_id = run.id

        # SME (admin) approves -> promotion updates the course CLO row.
        res = await client.post(
            f"{API}/stages/runs/{run_id}/approve",
            headers={"Authorization": f"Bearer {admin}"},
            json={"note": "looks good"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["review_status"] == "approved"

        res = await client.get(
            f"{API}/courses/{course_id}/clos",
            headers={"Authorization": f"Bearer {designer}"},
        )
        assert res.status_code == 200, res.text
        clo = res.json()["clos"][0]
        assert clo["statement"].startswith("Analyze the stages")
        assert clo["attributes"]["refined"] is True
        assert clo["attributes"]["original_statement"] == "Explain the water cycle"
        assert clo["attributes"]["bloom_level"] == "Analyze"
    finally:
        if course_id is not None:
            await _cleanup_clo_course(course_id)


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
