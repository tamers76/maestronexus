"""Integration tests for the runtime AI settings store (docs/10).

Driven through the ASGI app via httpx ``ASGITransport`` against the seeded dev
users + dev Postgres; skips cleanly if unavailable. Exercises masking, deep-merge
update, the resolved per-stage view, and reset-to-recommended. The tenant's
``ai_settings`` row is removed afterwards so the suite stays idempotent.

    cd backend; uv run pytest tests/ai_settings_test.py
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal, engine
from app.main import app
from app.modules.iam.models import Tenant, User
from app.modules.integrations.models import AiSettings

API = "/api/v1"
PASSWORD = "pass"
ADMIN_EMAIL = "admin"  # institution_admin -> integration.manage
LEARNER_EMAIL = "learner"  # no integration.manage

AI = f"{API}/integrations/ai-settings"


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


async def _cleanup_tenant_settings(email: str) -> None:
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            return
        await session.execute(
            delete(AiSettings).where(AiSettings.tenant_id == user.tenant_id)
        )
        await session.commit()


@pytest.fixture
async def client():
    await engine.dispose()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def test_get_settings_returns_catalog_and_resolved(client: AsyncClient):
    token = await _login(client, ADMIN_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed admin unavailable")
    try:
        resp = await client.get(AI, headers=_auth(token))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # All 12 stages present in the catalog + resolved view.
        assert len(body["catalog"]) == 12
        assert len(body["resolved"]) == 12
        assert "openai" in body["managed_providers"]
        # content_production defaults to council.
        cp = next(r for r in body["resolved"] if r["stage_key"] == "content_production")
        assert cp["mode"] == "council"
    finally:
        await _cleanup_tenant_settings(ADMIN_EMAIL)


async def test_api_key_is_masked_on_read(client: AsyncClient):
    token = await _login(client, ADMIN_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed admin unavailable")
    try:
        secret = "sk-test-1234567890abcdef"
        put = await client.put(
            AI,
            headers=_auth(token),
            json={"providers": {"openai": {"api_key": secret}}},
        )
        assert put.status_code == 200, put.text
        openai_cfg = put.json()["config"]["providers"]["openai"]
        assert openai_cfg["api_key"] != secret
        assert "\u2026" in openai_cfg["api_key"]  # masked with an ellipsis
        assert openai_cfg["configured"] is True

        # A subsequent update that echoes the masked value must NOT wipe the key.
        again = await client.put(
            AI,
            headers=_auth(token),
            json={"providers": {"openai": {"api_key": openai_cfg["api_key"]}}},
        )
        assert again.json()["config"]["providers"]["openai"]["configured"] is True
    finally:
        await _cleanup_tenant_settings(ADMIN_EMAIL)


async def test_update_council_flows_into_resolved_view(client: AsyncClient):
    token = await _login(client, ADMIN_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed admin unavailable")
    try:
        put = await client.put(
            AI,
            headers=_auth(token),
            json={"council": {"members": ["gpt-4o-mini", "gpt-4o"], "chairman": "gpt-4o"}},
        )
        assert put.status_code == 200, put.text
        resolved = put.json()["resolved"]
        cp = next(r for r in resolved if r["stage_key"] == "content_production")
        assert cp["council_models"] == ["gpt-4o-mini", "gpt-4o"]
        assert cp["chairman_model"] == "gpt-4o"
    finally:
        await _cleanup_tenant_settings(ADMIN_EMAIL)


async def test_reset_stage_prompts(client: AsyncClient):
    token = await _login(client, ADMIN_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed admin unavailable")
    try:
        put = await client.put(
            AI,
            headers=_auth(token),
            json={"stages": {"intake": {"member_system_prompt": "CUSTOM PROMPT"}}},
        )
        assert put.status_code == 200, put.text
        assert (
            put.json()["config"]["stages"]["intake"]["member_system_prompt"]
            == "CUSTOM PROMPT"
        )

        reset = await client.post(
            f"{AI}/stages/intake/reset-prompts", headers=_auth(token)
        )
        assert reset.status_code == 200, reset.text
        intake_cfg = reset.json()["config"]["stages"].get("intake", {})
        assert "member_system_prompt" not in intake_cfg
    finally:
        await _cleanup_tenant_settings(ADMIN_EMAIL)


async def test_settings_requires_permission(client: AsyncClient):
    # Unauthenticated -> 401.
    resp = await client.get(AI)
    assert resp.status_code == 401, resp.text

    # Learner lacks integration.manage -> 403.
    token = await _login(client, LEARNER_EMAIL)
    if token is None:
        pytest.skip("dev DB or seed learner unavailable")
    forbidden = await client.get(AI, headers=_auth(token))
    assert forbidden.status_code == 403, forbidden.text
