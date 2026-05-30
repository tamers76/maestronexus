"""Content & assessment slice tests (docs/07, docs/15 acceptance).

Covers the two acceptance criteria for this slice:
  * content/quizzes attach to nodes, and
  * only *approved* content is served to learners.

Plus the security invariant that ``answer_key`` never reaches a learner, and
that MCQ attempts are auto-graded.

These hit a real Postgres (the data model is migrated). If the DB or the demo
seed isn't available the integration tests skip rather than fail. The pure
grading unit test always runs. Storage (MinIO) tests skip when unreachable.
All rows created here are cleaned up in fixture teardown.
"""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.main import app
from app.modules.content.models import MediaAsset, Question
from app.modules.content.service import grade_responses

# ── Pure unit test (no external services) ────────────────────────────────────


def _q(qid: uuid.UUID, correct: object) -> Question:
    return Question(id=qid, assessment_id=uuid.uuid4(), type="mcq", answer_key={"correct": correct})


def test_grade_responses_scores_mcq() -> None:
    q1, q2, q3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    questions = [_q(q1, "a"), _q(q2, "b"), _q(q3, ["x", "y"])]
    responses = {str(q1): "a", str(q2): "c", str(q3): ["y", "x"]}
    # q1 correct, q2 wrong, q3 correct (order-insensitive) -> 2/3.
    assert grade_responses(questions, responses) == pytest.approx(2 / 3)


def test_grade_responses_none_when_not_gradable() -> None:
    essay = Question(id=uuid.uuid4(), assessment_id=uuid.uuid4(), type="essay", answer_key={})
    assert grade_responses([essay], {}) is None


# ── Integration fixtures ──────────────────────────────────────────────────────


@dataclass
class Graph:
    tenant_id: uuid.UUID
    designer_id: uuid.UUID
    learner_id: uuid.UUID
    node_id: uuid.UUID
    enrollment_id: uuid.UUID
    course_id: uuid.UUID
    class_id: uuid.UUID
    media_ids: list[uuid.UUID]


# Async tests + fixtures share one session-scoped event loop. The app's async
# engine (created at import) binds to a single loop; per-test loops would
# otherwise raise "attached to a different loop" on the 2nd DB test.
session_loop = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def graph():
    """Build a disposable course graph + enrollment owned by the seeded tenant."""

    from app.core.database import SessionLocal
    from app.modules.courses.models import Course, CourseVersion, LearningNode
    from app.modules.enrollment.models import Class, Enrollment
    from app.modules.iam.models import User

    # Connectivity probe: skip (don't fail) when Postgres isn't running.
    try:
        async with SessionLocal() as session:
            await session.execute(select(1))
    except Exception as exc:  # noqa: BLE001 - any connectivity issue -> skip
        pytest.skip(f"database unavailable: {exc!r}")

    async with SessionLocal() as session:
        designer = (
            await session.execute(select(User).where(User.email == "designer"))
        ).scalar_one_or_none()
        learner = (
            await session.execute(select(User).where(User.email == "learner"))
        ).scalar_one_or_none()
        if designer is None or learner is None:
            pytest.skip("demo seed users not present; run `uv run python -m app.seed`")

        course = Course(tenant_id=designer.tenant_id, title="ZZ Test Course", status="draft")
        session.add(course)
        await session.flush()
        cv = CourseVersion(course_id=course.id, version=1, state="draft")
        session.add(cv)
        await session.flush()
        node = LearningNode(course_version_id=cv.id, type="lesson", title="ZZ Test Node")
        session.add(node)
        await session.flush()
        klass = Class(tenant_id=designer.tenant_id, course_id=course.id, name="ZZ Test Class")
        session.add(klass)
        await session.flush()
        enrollment = Enrollment(
            tenant_id=designer.tenant_id,
            user_id=learner.id,
            class_id=klass.id,
            course_version_id=cv.id,
        )
        session.add(enrollment)
        await session.flush()

        g = Graph(
            tenant_id=designer.tenant_id,
            designer_id=designer.id,
            learner_id=learner.id,
            node_id=node.id,
            enrollment_id=enrollment.id,
            course_id=course.id,
            class_id=klass.id,
            media_ids=[],
        )
        await session.commit()

    yield g

    # ── Teardown: cascade-delete course + class wipes graph/content/quiz rows.
    async with SessionLocal() as session:
        for mid in g.media_ids:
            asset = await session.get(MediaAsset, mid)
            if asset is not None:
                await session.delete(asset)
        course = await session.get(Course, g.course_id)
        if course is not None:
            await session.delete(course)
        klass = await session.get(Class, g.class_id)
        if klass is not None:
            await session.delete(klass)
        await session.commit()


def _client(user_id: uuid.UUID, tenant_id: uuid.UUID) -> AsyncClient:
    token = create_access_token(user_id, tenant_id)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test/api/v1",
        headers={"Authorization": f"Bearer {token}"},
    )


# ── Integration tests ──────────────────────────────────────────────────────


@session_loop
async def test_approval_gate_controls_learner_visibility(graph: Graph) -> None:
    designer = _client(graph.designer_id, graph.tenant_id)
    learner = _client(graph.learner_id, graph.tenant_id)
    async with designer, learner:
        created = await designer.post(
            "/content/items",
            json={"node_id": str(graph.node_id), "modality": "text", "body": {"markdown": "hi"}},
        )
        assert created.status_code == 201, created.text
        item = created.json()
        assert item["approval_status"] == "draft"

        # Learner sees nothing while it's a draft.
        empty = await learner.get(f"/content/learner/items?node_id={graph.node_id}")
        assert empty.status_code == 200
        assert empty.json()["total"] == 0

        # Approve, then the learner can see it.
        approved = await designer.post(f"/content/items/{item['id']}/approve")
        assert approved.status_code == 200
        assert approved.json()["approval_status"] == "approved"

        visible = await learner.get(f"/content/learner/items?node_id={graph.node_id}")
        assert visible.json()["total"] == 1


@session_loop
async def test_quiz_autograde_and_answer_key_hidden(graph: Graph) -> None:
    designer = _client(graph.designer_id, graph.tenant_id)
    learner = _client(graph.learner_id, graph.tenant_id)
    async with designer, learner:
        assess = await designer.post(
            "/content/assessments",
            json={"node_id": str(graph.node_id), "type": "quiz", "config": {"title": "Q"}},
        )
        assert assess.status_code == 201, assess.text
        assessment_id = assess.json()["id"]

        q = await designer.post(
            f"/content/assessments/{assessment_id}/questions",
            json={
                "type": "mcq",
                "prompt": {"text": "2+2?", "options": [{"id": "a", "text": "4"}]},
                "answer_key": {"correct": "a"},
                "position": 0,
            },
        )
        assert q.status_code == 201, q.text
        question_id = q.json()["id"]

        # Learner view must not leak the answer key.
        learner_view = await learner.get(f"/content/learner/assessments/{assessment_id}")
        assert learner_view.status_code == 200
        payload = learner_view.json()
        assert payload["questions"][0].get("answer_key") is None
        assert "answer_key" not in payload["questions"][0]

        # Correct answer -> full score; key not echoed back.
        attempt = await learner.post(
            "/content/attempts",
            json={
                "enrollment_id": str(graph.enrollment_id),
                "assessment_id": assessment_id,
                "responses": {question_id: "a"},
            },
        )
        assert attempt.status_code == 201, attempt.text
        result = attempt.json()
        assert result["score"] == pytest.approx(1.0)
        assert "answer_key" not in result


@session_loop
async def test_learner_cannot_author(graph: Graph) -> None:
    learner = _client(graph.learner_id, graph.tenant_id)
    async with learner:
        resp = await learner.post(
            "/content/items",
            json={"node_id": str(graph.node_id), "modality": "text", "body": {}},
        )
        assert resp.status_code == 403


@session_loop
async def test_media_upload_roundtrip(graph: Graph) -> None:
    """Server-side upload to MinIO; skips cleanly when storage is unreachable."""

    from botocore.exceptions import BotoCoreError, ClientError

    designer = _client(graph.designer_id, graph.tenant_id)
    async with designer:
        payload = {
            "filename": "hello.txt",
            "mime_type": "text/plain",
            "content_base64": base64.b64encode(b"hello world").decode(),
        }
        resp = await designer.post("/content/media", json=payload)
        if resp.status_code == 502:
            pytest.skip("object storage (MinIO) unavailable")
        assert resp.status_code == 201, resp.text
        asset = resp.json()
        graph.media_ids.append(uuid.UUID(asset["id"]))
        assert asset["size_bytes"] == len(b"hello world")

        download = await designer.get(f"/content/media/{asset['id']}")
        try:
            assert download.status_code == 200
            assert download.json()["download_url"].startswith("http")
        except (BotoCoreError, ClientError):
            pytest.skip("object storage (MinIO) unavailable")
