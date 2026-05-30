"""Adaptive engine acceptance tests (docs/05, docs/15).

Covers: next-node returns a node + human-readable reason, persists a
recommendation, and a teacher override always wins over the engine.
"""

from __future__ import annotations

V1 = "/api/v1"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _enroll(client, world) -> str:
    resp = await client.post(
        f"{V1}/enrollment/classes",
        headers=auth(world.teacher_token),
        json={"course_id": str(world.course_id), "name": "Section A"},
    )
    class_id = resp.json()["id"]
    resp = await client.post(
        f"{V1}/enrollment/enrollments",
        headers=auth(world.teacher_token),
        json={
            "class_id": class_id,
            "email": world.learner_email,
            "course_version_id": str(world.version_id),
        },
    )
    return resp.json()["id"]


async def test_next_node_returns_node_with_reason(client, world):
    enrollment_id = await _enroll(client, world)

    resp = await client.get(
        f"{V1}/adaptive/enrollments/{enrollment_id}/next-node",
        headers=auth(world.learner_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Engine recommends the only available node (n1) with an explanation.
    assert body["recommended_node_id"] == str(world.node_ids["n1"])
    assert body["source"] == "engine"
    assert isinstance(body["reason"], str) and body["reason"].strip()
    assert body["recommendation_id"] is not None
    assert body["course_complete"] is False


async def test_teacher_override_wins(client, world):
    enrollment_id = await _enroll(client, world)

    # Engine would pick n1; teacher overrides to n2.
    resp = await client.post(
        f"{V1}/adaptive/enrollments/{enrollment_id}/next-node/override",
        headers=auth(world.teacher_token),
        json={"node_id": str(world.node_ids["n2"]), "reason": "Focus here first"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["source"] == "teacher_override"

    resp = await client.get(
        f"{V1}/adaptive/enrollments/{enrollment_id}/next-node",
        headers=auth(world.learner_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "teacher_override"
    assert body["recommended_node_id"] == str(world.node_ids["n2"])
    assert body["reason"] == "Focus here first"


async def test_override_requires_node_assign_permission(client, world):
    enrollment_id = await _enroll(client, world)

    resp = await client.post(
        f"{V1}/adaptive/enrollments/{enrollment_id}/next-node/override",
        headers=auth(world.learner_token),
        json={"node_id": str(world.node_ids["n2"])},
    )
    assert resp.status_code == 403, resp.text


async def test_course_complete_when_all_done(client, world):
    enrollment_id = await _enroll(client, world)
    for key in ("n1", "n2", "n3"):
        await client.post(
            f"{V1}/enrollment/enrollments/{enrollment_id}/nodes/{world.node_ids[key]}/complete",
            headers=auth(world.learner_token),
            json={},
        )
    resp = await client.get(
        f"{V1}/adaptive/enrollments/{enrollment_id}/next-node",
        headers=auth(world.learner_token),
    )
    body = resp.json()
    assert body["course_complete"] is True
    assert body["recommended_node_id"] is None
