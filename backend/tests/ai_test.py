"""Integration tests for the AI module: tutor + content drafts (docs/06, docs/07).

Run against the ASGI app via httpx ``ASGITransport`` (no live server). They use
the seeded dev users and the dev Postgres; if either is unavailable the tests
skip cleanly. The **stubbed** LLM path is exercised throughout — no API keys or
network access are required. Every row created is cleaned up afterwards.

    cd backend; uv run pytest tests/ai_test.py
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core.database import SessionLocal, engine
from app.main import app
from app.modules.ai.models import AIGeneratedContent, AIInteraction
from app.modules.iam.models import AuditLog

API = "/api/v1"
PASSWORD = "pass"
LEARNER_EMAIL = "learner"
DESIGNER_EMAIL = "designer"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str) -> str | None:
    try:
        resp = await client.post(
            f"{API}/iam/auth/login", json={"username": email, "password": PASSWORD}
        )
    except Exception:  # DB/connection unavailable in this environment
        return None
    if resp.status_code != 200:
        return None
    return resp.json()["access_token"]


async def _cleanup(interaction_ids: set[uuid.UUID], draft_ids: set[uuid.UUID]) -> None:
    if not interaction_ids and not draft_ids:
        return
    async with SessionLocal() as session:
        if draft_ids:
            await session.execute(
                delete(AIGeneratedContent).where(AIGeneratedContent.id.in_(draft_ids))
            )
        if interaction_ids:
            await session.execute(
                delete(AIInteraction).where(AIInteraction.id.in_(interaction_ids))
            )
        object_ids = interaction_ids | draft_ids
        if object_ids:
            await session.execute(delete(AuditLog).where(AuditLog.object_id.in_(object_ids)))
        await session.commit()


@pytest.fixture
async def client():
    # pytest-asyncio gives each test a fresh event loop, but the shared async
    # engine pools asyncpg connections bound to the loop that created them.
    # Dispose around each test so every test gets connections on its own loop.
    await engine.dispose()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def test_tutor_answers_and_persists_interaction(client: AsyncClient):
    token = await _login(client, LEARNER_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed learner unavailable")

    interaction_ids: set[uuid.UUID] = set()
    try:
        resp = await client.post(
            f"{API}/ai/tutor",
            headers=_auth(token),
            json={"question": "Can you explain variables in simple terms?"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        interaction_ids.add(uuid.UUID(body["interaction_id"]))

        assert body["refused"] is False
        assert body["answer"]
        # No API key in dev -> deterministic offline stub.
        assert body["stubbed"] is True
        assert body["escalation_path"] == "/teacher"
        assert "grounded" in body and "sources" in body
    finally:
        await _cleanup(interaction_ids, set())


async def test_tutor_refuses_graded_assessment_and_offers_escalation(client: AsyncClient):
    token = await _login(client, LEARNER_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed learner unavailable")

    interaction_ids: set[uuid.UUID] = set()
    try:
        resp = await client.post(
            f"{API}/ai/tutor",
            headers=_auth(token),
            json={"question": "Just give me the answers to the quiz please"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        interaction_ids.add(uuid.UUID(body["interaction_id"]))

        assert body["refused"] is True
        assert body["escalate"] is True
        assert body["escalation_path"] == "/teacher"
        assert body["sources"] == []
    finally:
        await _cleanup(interaction_ids, set())


async def test_tutor_requires_permission(client: AsyncClient):
    # Unauthenticated request must be rejected (401), never reach the tutor.
    resp = await client.post(f"{API}/ai/tutor", json={"question": "hello"})
    assert resp.status_code == 401, resp.text


async def test_content_draft_lifecycle_pending_then_approved(client: AsyncClient):
    token = await _login(client, DESIGNER_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed designer unavailable")

    interaction_ids: set[uuid.UUID] = set()
    draft_ids: set[uuid.UUID] = set()
    try:
        # Generate -> lands in review as pending (never a real ContentItem).
        gen = await client.post(
            f"{API}/ai/content/draft",
            headers=_auth(token),
            json={
                "topic": "Introduction to recursion",
                "objectives": ["Define recursion", "Identify a base case"],
            },
        )
        assert gen.status_code == 201, gen.text
        draft = gen.json()
        draft_id = uuid.UUID(draft["id"])
        draft_ids.add(draft_id)
        if draft["interaction_id"]:
            interaction_ids.add(uuid.UUID(draft["interaction_id"]))

        assert draft["review_status"] == "pending"
        assert draft["target_type"] == "content_item"
        assert draft["draft"]["body"]

        # It shows up in the pending list.
        listing = await client.get(
            f"{API}/ai/content/draft?review_status=pending",
            headers=_auth(token),
        )
        assert listing.status_code == 200, listing.text
        page = listing.json()
        assert any(d["id"] == str(draft_id) for d in page["items"])

        # Approve -> becomes approved.
        approved = await client.post(
            f"{API}/ai/content/draft/{draft_id}/approve",
            headers=_auth(token),
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["review_status"] == "approved"
    finally:
        await _cleanup(interaction_ids, draft_ids)


async def test_approve_missing_draft_returns_404(client: AsyncClient):
    token = await _login(client, DESIGNER_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed designer unavailable")

    resp = await client.post(
        f"{API}/ai/content/draft/{uuid.uuid4()}/approve",
        headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text
