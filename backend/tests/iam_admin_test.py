"""Integration tests for the IAM admin surface (users, roles, audit).

Run (DB + seed required) from the backend dir:

    uv run pytest tests/iam_admin_test.py

Uses httpx ASGITransport against the FastAPI app. Created rows are cleaned up
so the shared dev database stays tidy.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.modules.iam.models import AuditLog, User, UserRole

API = "/api/v1"
ADMIN_EMAIL = "admin"
TEACHER_EMAIL = "teacher"
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


async def _cleanup_user(user_id: uuid.UUID) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(UserRole).where(UserRole.user_id == user_id))
        await session.execute(delete(AuditLog).where(AuditLog.object_id == user_id))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


@pytest.mark.asyncio
async def test_user_lifecycle_and_audit() -> None:
    async with _client() as client:
        token = await _login(client, ADMIN_EMAIL)
        headers = _auth(token)
        email = f"pytest-{uuid.uuid4().hex[:10]}@the-code.dev"
        created_id: uuid.UUID | None = None
        try:
            # Create
            res = await client.post(
                f"{API}/iam/users",
                headers=headers,
                json={
                    "email": email,
                    "display_name": "Pytest User",
                    "password": "supersecret123",
                    "role_keys": ["teacher"],
                },
            )
            assert res.status_code == 201, res.text
            body = res.json()
            created_id = uuid.UUID(body["id"])
            assert body["email"] == email
            assert "teacher" in body["roles"]

            # Duplicate email rejected
            dup = await client.post(
                f"{API}/iam/users",
                headers=headers,
                json={"email": email, "display_name": "Dup", "password": "supersecret123"},
            )
            assert dup.status_code == 409, dup.text

            # List finds the new user
            listed = await client.get(
                f"{API}/iam/users", headers=headers, params={"search": "pytest-"}
            )
            assert listed.status_code == 200
            assert listed.json()["total"] >= 1

            # Get
            got = await client.get(f"{API}/iam/users/{created_id}", headers=headers)
            assert got.status_code == 200
            assert got.json()["email"] == email

            # Status update
            patched = await client.patch(
                f"{API}/iam/users/{created_id}/status",
                headers=headers,
                json={"status": "suspended"},
            )
            assert patched.status_code == 200
            assert patched.json()["status"] == "suspended"

            # Assign + unassign a role
            assigned = await client.post(
                f"{API}/iam/users/{created_id}/roles",
                headers=headers,
                json={"role_key": "learner"},
            )
            assert assigned.status_code == 200
            assert "learner" in assigned.json()["roles"]

            removed = await client.delete(
                f"{API}/iam/users/{created_id}/roles/learner", headers=headers
            )
            assert removed.status_code == 200
            assert "learner" not in removed.json()["roles"]

            # Audit log captured the create
            audit = await client.get(
                f"{API}/iam/audit-logs", headers=headers, params={"action": "user.create"}
            )
            assert audit.status_code == 200
            actions = {e["action"] for e in audit.json()["items"]}
            assert "user.create" in actions
        finally:
            if created_id is not None:
                await _cleanup_user(created_id)


@pytest.mark.asyncio
async def test_roles_and_permission_catalog() -> None:
    async with _client() as client:
        headers = _auth(await _login(client, ADMIN_EMAIL))

        roles = await client.get(f"{API}/iam/roles", headers=headers)
        assert roles.status_code == 200
        keys = {r["key"] for r in roles.json()}
        assert {"institution_admin", "teacher", "learner"} <= keys

        perms = await client.get(f"{API}/iam/permissions", headers=headers)
        assert perms.status_code == 200
        perm_keys = {p["key"] for p in perms.json()}
        assert {"user.manage", "audit.read", "report.view_class"} <= perm_keys


@pytest.mark.asyncio
async def test_rbac_blocks_out_of_scope_actions() -> None:
    async with _client() as client:
        teacher = _auth(await _login(client, TEACHER_EMAIL))
        # Teacher lacks user.manage and audit.read -> 403 on admin endpoints.
        assert (await client.get(f"{API}/iam/users", headers=teacher)).status_code == 403
        assert (await client.get(f"{API}/iam/audit-logs", headers=teacher)).status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_rejected() -> None:
    async with _client() as client:
        assert (await client.get(f"{API}/iam/users")).status_code == 401
