"""Integration tests for the analytics module (reports + dashboards).

Run (DB + seed required) from the backend dir:

    uv run pytest tests/analytics_test.py
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

API = "/api/v1"
ADMIN_EMAIL = "admin"
TEACHER_EMAIL = "teacher"
LEARNER_EMAIL = "learner"
PASSWORD = "pass"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _login(client: AsyncClient, email: str) -> str:
    res = await client.post(
        f"{API}/iam/auth/login", json={"username": email, "password": PASSWORD}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_institution_dashboard_for_admin() -> None:
    async with _client() as client:
        headers = _auth(await _login(client, ADMIN_EMAIL))
        res = await client.get(f"{API}/analytics/dashboard/institution", headers=headers)
        assert res.status_code == 200, res.text
        body = res.json()
        assert set(body) == {"totals", "engagement", "top_classes", "users_by_role"}
        assert body["totals"]["users"] >= 1
        assert 0 <= body["engagement"]["avg_completion_pct"] <= 100
        assert 0 <= body["engagement"]["attendance_rate"] <= 100


@pytest.mark.asyncio
async def test_report_classes_scoping() -> None:
    async with _client() as client:
        admin = _auth(await _login(client, ADMIN_EMAIL))
        teacher = _auth(await _login(client, TEACHER_EMAIL))

        # Both can hit the class list (admins = all, teachers = own).
        assert (await client.get(f"{API}/analytics/classes", headers=admin)).status_code == 200
        assert (await client.get(f"{API}/analytics/classes", headers=teacher)).status_code == 200


@pytest.mark.asyncio
async def test_dashboard_requires_institution_permission() -> None:
    async with _client() as client:
        teacher = _auth(await _login(client, TEACHER_EMAIL))
        # Teacher has report.view_class but not dashboard.view_institution.
        res = await client.get(f"{API}/analytics/dashboard/institution", headers=teacher)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_reports_blocked_for_learner() -> None:
    async with _client() as client:
        learner = _auth(await _login(client, LEARNER_EMAIL))
        # Learner lacks report.view_class entirely.
        assert (await client.get(f"{API}/analytics/classes", headers=learner)).status_code == 403


@pytest.mark.asyncio
async def test_unknown_class_returns_404() -> None:
    import uuid

    async with _client() as client:
        admin = _auth(await _login(client, ADMIN_EMAIL))
        res = await client.get(
            f"{API}/analytics/classes/{uuid.uuid4()}/report", headers=admin
        )
        assert res.status_code == 404
