"""Attendance API tests (docs/09): class-scoped sessions + per-learner records."""

from __future__ import annotations

from datetime import UTC, datetime

API = "/api/v1"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_session_and_marking_is_class_scoped(client, world):
    w = world
    when = datetime.now(UTC).isoformat()

    # Teacher lists their own classes.
    res = await client.get(f"{API}/attendance/classes", headers=_auth(w.teacher_token))
    assert res.status_code == 200, res.text
    class_ids = {c["id"] for c in res.json()}
    assert str(w.class_id) in class_ids
    assert str(w.other_class_id) not in class_ids

    # Teacher creates a session for their class.
    res = await client.post(
        f"{API}/attendance/sessions",
        headers=_auth(w.teacher_token),
        json={"class_id": str(w.class_id), "scheduled_at": when, "mode": "in_person"},
    )
    assert res.status_code == 200, res.text
    session_id = res.json()["id"]

    # Roster includes the enrolled learner, initially unmarked.
    res = await client.get(
        f"{API}/attendance/sessions/{session_id}/roster", headers=_auth(w.teacher_token)
    )
    assert res.status_code == 200, res.text
    roster = res.json()
    learner_ids = {e["learner_id"] for e in roster}
    assert str(w.learner_id) in learner_ids
    assert all(e["status"] is None for e in roster)

    # Mark the learner late.
    res = await client.post(
        f"{API}/attendance/sessions/{session_id}/records",
        headers=_auth(w.teacher_token),
        json={"records": [{"learner_id": str(w.learner_id), "status": "late"}]},
    )
    assert res.status_code == 200, res.text
    records = res.json()
    assert len(records) == 1
    assert records[0]["status"] == "late"
    assert records[0]["marked_by"] == str(w.teacher_id)
    assert records[0]["marked_at"] is not None

    # Re-marking upserts (no duplicate row, status updates).
    res = await client.post(
        f"{API}/attendance/sessions/{session_id}/records",
        headers=_auth(w.teacher_token),
        json={"records": [{"learner_id": str(w.learner_id), "status": "present"}]},
    )
    assert res.status_code == 200, res.text
    records = res.json()
    assert len(records) == 1
    assert records[0]["status"] == "present"


async def test_other_teacher_cannot_create_or_read_session(client, world):
    w = world
    when = datetime.now(UTC).isoformat()

    # Another teacher cannot create a session for a class they don't teach.
    res = await client.post(
        f"{API}/attendance/sessions",
        headers=_auth(w.other_teacher_token),
        json={"class_id": str(w.class_id), "scheduled_at": when},
    )
    assert res.status_code == 403, res.text

    # Owning teacher creates one.
    res = await client.post(
        f"{API}/attendance/sessions",
        headers=_auth(w.teacher_token),
        json={"class_id": str(w.class_id), "scheduled_at": when},
    )
    assert res.status_code == 200, res.text
    session_id = res.json()["id"]

    # The other teacher cannot read it or its roster (object-level scope).
    res = await client.get(
        f"{API}/attendance/sessions/{session_id}", headers=_auth(w.other_teacher_token)
    )
    assert res.status_code == 403, res.text

    res = await client.get(
        f"{API}/attendance/sessions/{session_id}/roster",
        headers=_auth(w.other_teacher_token),
    )
    assert res.status_code == 403, res.text


async def test_cannot_mark_learner_outside_class(client, world):
    w = world
    when = datetime.now(UTC).isoformat()

    res = await client.post(
        f"{API}/attendance/sessions",
        headers=_auth(w.teacher_token),
        json={"class_id": str(w.class_id), "scheduled_at": when},
    )
    assert res.status_code == 200, res.text
    session_id = res.json()["id"]

    # other_learner belongs to a different class -> rejected.
    res = await client.post(
        f"{API}/attendance/sessions/{session_id}/records",
        headers=_auth(w.teacher_token),
        json={"records": [{"learner_id": str(w.other_learner_id), "status": "present"}]},
    )
    assert res.status_code == 403, res.text


async def test_learner_lacks_attendance_permission(client, world):
    res = await client.get(f"{API}/attendance/classes", headers=_auth(world.learner_token))
    assert res.status_code == 403, res.text
