"""Enrollment & progress acceptance tests (docs/15).

Covers: class create, enroll (pinned version), node-state initialization, and the
``locked → available → completed/mastered`` transitions with prerequisite unlocking.
"""

from __future__ import annotations

V1 = "/api/v1"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_class(client, world) -> str:
    resp = await client.post(
        f"{V1}/enrollment/classes",
        headers=auth(world.teacher_token),
        json={"course_id": str(world.course_id), "name": "Section A"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _enroll(client, world, class_id: str) -> str:
    resp = await client.post(
        f"{V1}/enrollment/enrollments",
        headers=auth(world.teacher_token),
        json={
            "class_id": class_id,
            "email": world.learner_email,
            "course_version_id": str(world.version_id),
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["course_version_id"] == str(world.version_id)
    return body["id"]


def _states(detail: dict) -> dict[str, str]:
    return {n["node_title"]: n["state"] for n in detail["nodes"]}


async def test_enroll_initializes_node_states(client, world):
    class_id = await _create_class(client, world)
    enrollment_id = await _enroll(client, world, class_id)

    resp = await client.get(
        f"{V1}/enrollment/enrollments/{enrollment_id}",
        headers=auth(world.teacher_token),
    )
    assert resp.status_code == 200, resp.text
    states = _states(resp.json())
    # n1 has no prerequisites; n2 requires n1; n3 is gated behind n2 mastery.
    assert states["1. Intro"] == "available"
    assert states["2. Basics"] == "locked"
    assert states["3. Advanced"] == "locked"


async def test_completion_unlocks_dependents(client, world):
    class_id = await _create_class(client, world)
    enrollment_id = await _enroll(client, world, class_id)

    # Learner completes n1 -> mastered (no explicit rule) -> unlocks n2 (requires).
    resp = await client.post(
        f"{V1}/enrollment/enrollments/{enrollment_id}/nodes/{world.node_ids['n1']}/complete",
        headers=auth(world.learner_token),
        json={"time_spent_seconds": 60},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["node"]["state"] == "mastered"
    assert str(world.node_ids["n2"]) in body["unlocked_node_ids"]

    # n3 stays locked until n2 is mastered (mastery_gate).
    resp = await client.post(
        f"{V1}/enrollment/enrollments/{enrollment_id}/nodes/{world.node_ids['n2']}/complete",
        headers=auth(world.learner_token),
        json={"time_spent_seconds": 30},
    )
    assert resp.status_code == 200, resp.text
    assert str(world.node_ids["n3"]) in resp.json()["unlocked_node_ids"]

    resp = await client.get(
        f"{V1}/enrollment/enrollments/{enrollment_id}",
        headers=auth(world.learner_token),
    )
    states = _states(resp.json())
    assert states["3. Advanced"] == "available"


async def test_cannot_complete_locked_node(client, world):
    class_id = await _create_class(client, world)
    enrollment_id = await _enroll(client, world, class_id)

    resp = await client.post(
        f"{V1}/enrollment/enrollments/{enrollment_id}/nodes/{world.node_ids['n2']}/complete",
        headers=auth(world.learner_token),
        json={},
    )
    assert resp.status_code == 409, resp.text


async def test_learner_cannot_manage_classes(client, world):
    resp = await client.post(
        f"{V1}/enrollment/classes",
        headers=auth(world.learner_token),
        json={"course_id": str(world.course_id), "name": "Nope"},
    )
    assert resp.status_code == 403, resp.text
