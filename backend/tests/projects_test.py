"""Projects API tests (docs/08): per-learner submission + object-scoped grading."""

from __future__ import annotations

API = "/api/v1"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_full_grading_flow_is_class_scoped(client, world):
    w = world

    # Teacher creates a project on the node + a rubric.
    res = await client.post(
        f"{API}/projects",
        headers=_auth(w.teacher_token),
        json={
            "node_id": str(w.node_id),
            "title": "Build a CLI",
            "instructions": {"text": "Ship a small command-line tool."},
            "max_submissions": 2,
        },
    )
    assert res.status_code == 200, res.text
    project_id = res.json()["id"]

    res = await client.put(
        f"{API}/projects/{project_id}/rubric",
        headers=_auth(w.teacher_token),
        json={"criteria": {"items": [{"key": "quality", "label": "Quality", "max": 10}]}},
    )
    assert res.status_code == 200, res.text

    # Learner submits their own work (per-learner).
    res = await client.post(
        f"{API}/projects/{project_id}/submissions",
        headers=_auth(w.learner_token),
        json={"payload": {"text": "Here is my tool"}},
    )
    assert res.status_code == 200, res.text
    submission = res.json()
    submission_id = submission["id"]
    assert submission["learner_id"] == str(w.learner_id)
    assert submission["attempt_no"] == 1

    # The submission shows up in the owning teacher's grading queue...
    res = await client.get(f"{API}/projects/submissions", headers=_auth(w.teacher_token))
    assert res.status_code == 200, res.text
    queue_ids = {item["id"] for item in res.json()["items"]}
    assert submission_id in queue_ids

    # ...but NOT in another teacher's queue (object-level scope).
    res = await client.get(
        f"{API}/projects/submissions", headers=_auth(w.other_teacher_token)
    )
    assert res.status_code == 200, res.text
    assert submission_id not in {item["id"] for item in res.json()["items"]}

    # Another teacher cannot open or grade it.
    res = await client.get(
        f"{API}/projects/submissions/{submission_id}",
        headers=_auth(w.other_teacher_token),
    )
    assert res.status_code == 403, res.text

    res = await client.post(
        f"{API}/projects/submissions/{submission_id}/grade",
        headers=_auth(w.other_teacher_token),
        json={"score": 9, "rubric_scores": {"quality": 9}, "feedback": "nope"},
    )
    assert res.status_code == 403, res.text

    # The owning teacher grades it with rubric scores + feedback.
    res = await client.post(
        f"{API}/projects/submissions/{submission_id}/grade",
        headers=_auth(w.teacher_token),
        json={"score": 8.5, "rubric_scores": {"quality": 8}, "feedback": "Solid work."},
    )
    assert res.status_code == 200, res.text
    result = res.json()
    assert result["grade"]["score"] == 8.5
    assert result["grade"]["rubric_scores"] == {"quality": 8}
    assert result["feedback"]["body"] == "Solid work."

    # Detail now reflects the grade + feedback and is marked graded.
    res = await client.get(
        f"{API}/projects/submissions/{submission_id}", headers=_auth(w.teacher_token)
    )
    assert res.status_code == 200, res.text
    detail = res.json()
    assert detail["grade"]["score"] == 8.5
    assert detail["feedback"]["body"] == "Solid work."
    assert detail["submission"]["status"] == "graded"


async def test_learner_cannot_grade_and_respects_submission_limit(client, world):
    w = world

    res = await client.post(
        f"{API}/projects",
        headers=_auth(w.teacher_token),
        json={"node_id": str(w.node_id), "title": "One-shot", "max_submissions": 1},
    )
    assert res.status_code == 200, res.text
    project_id = res.json()["id"]

    # First submission ok.
    res = await client.post(
        f"{API}/projects/{project_id}/submissions",
        headers=_auth(w.learner_token),
        json={"payload": {"text": "attempt 1"}},
    )
    assert res.status_code == 200, res.text

    # Second submission rejected (max_submissions = 1).
    res = await client.post(
        f"{API}/projects/{project_id}/submissions",
        headers=_auth(w.learner_token),
        json={"payload": {"text": "attempt 2"}},
    )
    assert res.status_code == 409, res.text

    # A learner lacks project.grade -> cannot reach the grading queue.
    res = await client.get(f"{API}/projects/submissions", headers=_auth(w.learner_token))
    assert res.status_code == 403, res.text


async def test_learner_not_in_class_cannot_submit(client, world):
    w = world

    res = await client.post(
        f"{API}/projects",
        headers=_auth(w.teacher_token),
        json={"node_id": str(w.node_id), "title": "Scoped", "max_submissions": 1},
    )
    assert res.status_code == 200, res.text
    project_id = res.json()["id"]

    # other_learner is enrolled in a different class on the same course version,
    # so they DO have an enrollment and may submit their own work.
    res = await client.post(
        f"{API}/projects/{project_id}/submissions",
        headers=_auth(w.other_learner_token),
        json={"payload": {"text": "mine"}},
    )
    assert res.status_code == 200, res.text

    # But the first teacher must not see another class's submission.
    res = await client.get(f"{API}/projects/submissions", headers=_auth(w.teacher_token))
    assert res.status_code == 200, res.text
    learner_ids = {item["learner_id"] for item in res.json()["items"]}
    assert str(w.other_learner_id) not in learner_ids
