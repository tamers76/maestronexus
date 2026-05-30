"""Integration tests for the stages module (stages-as-features + council).

Driven through the ASGI app via httpx ``ASGITransport`` against the seeded dev
users + dev Postgres; skips cleanly if unavailable. Everything runs on the
**offline LLM stub** (no API keys / network). Covers the catalog, single + council
runs, stage independence (run a downstream stage with no upstream), risk/review
routing, SME approve/reject, and permission gating. All created rows are removed.

    cd backend; uv run pytest tests/stages_test.py
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal, engine
from app.main import app
from app.modules.ai.models import AIGeneratedContent, AIInteraction
from app.modules.courses.models import Course
from app.modules.iam.models import AuditLog
from app.modules.stages.models import StageRun

API = "/api/v1"
PASSWORD = "pass"
DESIGNER_EMAIL = "designer"  # course.manage + stage.run, NOT stage.review
ADMIN_EMAIL = "admin"  # institution_admin -> stage.review
LEARNER_EMAIL = "learner"  # no stage.run


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str) -> str | None:
    try:
        resp = await client.post(
            f"{API}/iam/auth/login", json={"username": email, "password": PASSWORD}
        )
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    return resp.json()["access_token"]


async def _create_course(client: AsyncClient, token: str) -> str | None:
    resp = await client.post(
        f"{API}/courses",
        headers=_auth(token),
        json={"title": f"Stage Test {uuid.uuid4().hex[:6]}", "description": "test"},
    )
    if resp.status_code not in (200, 201):
        return None
    return resp.json()["id"]


async def _cleanup_course(course_id: str) -> None:
    async with SessionLocal() as session:
        cid = uuid.UUID(course_id)
        run_ids = (
            (await session.execute(select(StageRun.id).where(StageRun.course_id == cid)))
            .scalars()
            .all()
        )
        # Content drafts promoted by content_production (via their interactions).
        inter_ids = (
            (
                await session.execute(
                    select(AIInteraction.id).where(
                        AIInteraction.agent == "stage_content_production",
                        AIInteraction.context_refs["course_id"].astext == course_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        if inter_ids:
            await session.execute(
                delete(AIGeneratedContent).where(
                    AIGeneratedContent.interaction_id.in_(inter_ids)
                )
            )
            await session.execute(
                delete(AIInteraction).where(AIInteraction.id.in_(inter_ids))
            )
        if run_ids:
            await session.execute(delete(AuditLog).where(AuditLog.object_id.in_(run_ids)))
            await session.execute(delete(StageRun).where(StageRun.id.in_(run_ids)))
        await session.execute(delete(Course).where(Course.id == cid))
        await session.commit()


@pytest.fixture
async def client():
    await engine.dispose()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def test_catalog_has_eighteen_blueprint_stages(client: AsyncClient):
    token = await _login(client, DESIGNER_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed designer unavailable")
    resp = await client.get(f"{API}/stages", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    catalog = resp.json()
    assert len(catalog) == 18
    keys = {c["key"] for c in catalog}
    # First and last Blueprint stages plus a few renamed ones.
    assert "intake" in keys and "analytics" in keys
    assert {"clo_review", "assessment_weighting", "mastery_nodes", "node_relationships"} <= keys
    # Legacy keys are exposed as aliases, never as canonical keys.
    by_key = {c["key"]: c for c in catalog}
    assert "clo_refinement" in by_key["clo_review"]["aliases"]
    assert "assessment_rubrics" in by_key["assessment_weighting"]["aliases"]
    assert "mastery_node_design" in by_key["mastery_nodes"]["aliases"]
    assert "node_relationship_map" in by_key["node_relationships"]["aliases"]
    assert "clo_refinement" not in keys


async def test_single_run_succeeds_with_stub(client: AsyncClient):
    token = await _login(client, DESIGNER_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed designer unavailable")
    course_id = await _create_course(client, token)
    if course_id is None:
        pytest.skip("could not create course")
    try:
        resp = await client.post(
            f"{API}/stages/courses/{course_id}/stages/intake/run",
            headers=_auth(token),
            json={"mode": "single"},
        )
        assert resp.status_code == 200, resp.text
        run = resp.json()
        assert run["status"] == "succeeded"
        assert run["execution_mode"] == "single"
        assert run["review_status"] == "auto_ok"  # low-risk stage
        # Works on the offline stub or a live model; both produce an artifact.
        assert run["output"]["output_kind"] == "course_contract"
        assert "stubbed" in run["output"]
    finally:
        await _cleanup_course(course_id)


async def test_legacy_stage_key_alias_resolves(client: AsyncClient):
    # A run posted under a legacy stage_key resolves to the canonical stage.
    token = await _login(client, DESIGNER_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed designer unavailable")
    course_id = await _create_course(client, token)
    if course_id is None:
        pytest.skip("could not create course")
    try:
        resp = await client.post(
            f"{API}/stages/courses/{course_id}/stages/clo_refinement/run",
            headers=_auth(token),
            json={"mode": "single"},
        )
        assert resp.status_code == 200, resp.text
        run = resp.json()
        # Stored canonically; clo_review is a high-risk council stage.
        assert run["stage_key"] == "clo_review"
        assert run["status"] == "succeeded"
        assert run["review_status"] == "needs_review"
    finally:
        await _cleanup_course(course_id)


async def test_council_run_records_transcript(client: AsyncClient):
    token = await _login(client, DESIGNER_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed designer unavailable")
    course_id = await _create_course(client, token)
    if course_id is None:
        pytest.skip("could not create course")
    try:
        resp = await client.post(
            f"{API}/stages/courses/{course_id}/stages/clo_review/run",
            headers=_auth(token),
            json={"mode": "council"},
        )
        assert resp.status_code == 200, resp.text
        run = resp.json()
        assert run["status"] == "succeeded"
        assert run["execution_mode"] == "council"
        members = run["council_transcript"]["members"]
        assert len(members) >= 1
        assert run["output"]["text"]
    finally:
        await _cleanup_course(course_id)


async def test_stage_is_independent_of_upstream(client: AsyncClient):
    # A late-stage feature runs even when no upstream artifacts exist.
    token = await _login(client, DESIGNER_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed designer unavailable")
    course_id = await _create_course(client, token)
    if course_id is None:
        pytest.skip("could not create course")
    try:
        resp = await client.post(
            f"{API}/stages/courses/{course_id}/stages/analytics/run",
            headers=_auth(token),
            json={"mode": "single"},
        )
        assert resp.status_code == 200, resp.text
        run = resp.json()
        assert run["status"] == "succeeded"
        # No upstream runs were resolved (nothing was blocked).
        assert run["input_refs"]["upstream_runs"] == {}
    finally:
        await _cleanup_course(course_id)


async def test_high_risk_stage_routes_to_review_and_sme_approves(client: AsyncClient):
    designer = await _login(client, DESIGNER_EMAIL)
    admin = await _login(client, ADMIN_EMAIL)
    if designer is None or admin is None:
        pytest.skip("dev DB or seed users unavailable")
    course_id = await _create_course(client, designer)
    if course_id is None:
        pytest.skip("could not create course")
    try:
        run_resp = await client.post(
            f"{API}/stages/courses/{course_id}/stages/assessment_redesign/run",
            headers=_auth(designer),
            json={"mode": "single"},
        )
        assert run_resp.status_code == 200, run_resp.text
        run = run_resp.json()
        assert run["review_status"] == "needs_review"  # high-risk stage
        run_id = run["id"]

        # Designer cannot review (no stage.review).
        forbidden = await client.post(
            f"{API}/stages/runs/{run_id}/approve", headers=_auth(designer), json={}
        )
        assert forbidden.status_code == 403, forbidden.text

        # Admin (SME) approves.
        approved = await client.post(
            f"{API}/stages/runs/{run_id}/approve",
            headers=_auth(admin),
            json={"note": "Looks good"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["review_status"] == "approved"

        # Reject path on a fresh run.
        run2 = (
            await client.post(
                f"{API}/stages/courses/{course_id}/stages/assessment_redesign/run",
                headers=_auth(designer),
                json={"mode": "single"},
            )
        ).json()
        rejected = await client.post(
            f"{API}/stages/runs/{run2['id']}/reject", headers=_auth(admin), json={}
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["review_status"] == "rejected"
    finally:
        await _cleanup_course(course_id)


async def test_run_requires_permission(client: AsyncClient):
    # Unauthenticated -> 401.
    resp = await client.post(
        f"{API}/stages/courses/{uuid.uuid4()}/stages/intake/run", json={}
    )
    assert resp.status_code == 401, resp.text

    # Learner lacks stage.run -> 403.
    token = await _login(client, LEARNER_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed learner unavailable")
    forbidden = await client.post(
        f"{API}/stages/courses/{uuid.uuid4()}/stages/intake/run",
        headers=_auth(token),
        json={},
    )
    assert forbidden.status_code == 403, forbidden.text
