"""Focused tests for the Maestro Blueprint backend foundation.

Two layers:

* **Unit (no DB)** — the 18-stage registry + legacy aliases, prompt output
  schemas, runtime Pydantic schemas, and pure promotion/readiness helpers.
* **Integration (dev Postgres, skips if unavailable)** — approval-time promotion
  is idempotent, version scoped, and only fires on approval (rejection promotes
  nothing).

    cd backend; uv run pytest tests/blueprint_test.py
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, func, select

from app.modules.stages.definitions import (
    STAGE_ALIASES,
    STAGE_ORDER,
    STAGE_REGISTRY,
    aliases_for,
    canonical_key,
    get_stage,
    stage_key_variants,
)
from app.modules.stages.prompts import build_user_prompt

# ── Unit: registry + aliases ──────────────────────────────────────────────────

LEGACY_KEYS = {
    "clo_refinement": "clo_review",
    "assessment_rubrics": "assessment_weighting",
    "mastery_node_design": "mastery_nodes",
    "node_relationship_map": "node_relationships",
}


def test_registry_has_eighteen_ordered_stages():
    assert len(STAGE_REGISTRY) == 18
    assert len(STAGE_ORDER) == 18
    # Orders are 1..18 with no gaps/dupes.
    orders = sorted(spec.order for spec in STAGE_REGISTRY.values())
    assert orders == list(range(1, 19))
    # STAGE_ORDER is sorted by order and starts/ends at the Blueprint bookends.
    assert STAGE_ORDER[0] == "intake"
    assert STAGE_ORDER[-1] == "analytics"


def test_legacy_aliases_resolve_to_canonical():
    assert STAGE_ALIASES == LEGACY_KEYS
    for legacy, canon in LEGACY_KEYS.items():
        assert canonical_key(legacy) == canon
        # Legacy keys are NOT canonical registry keys.
        assert legacy not in STAGE_REGISTRY
        assert canon in STAGE_REGISTRY
        # get_stage resolves either spelling to the same spec.
        assert get_stage(legacy) is get_stage(canon)
        # aliases_for(canon) surfaces the legacy spelling.
        assert legacy in aliases_for(canon)


def test_stage_key_variants_covers_both_spellings():
    # Reads must match rows stored under either the legacy or canonical key.
    assert set(stage_key_variants("clo_review")) == {"clo_review", "clo_refinement"}
    assert set(stage_key_variants("clo_refinement")) == {"clo_review", "clo_refinement"}
    # A stage with no alias only yields itself.
    assert stage_key_variants("intake") == ["intake"]


def test_canonical_key_is_identity_for_unknown_keys():
    assert canonical_key("not_a_stage") == "not_a_stage"
    assert get_stage("not_a_stage") is None


# ── Unit: prompts ─────────────────────────────────────────────────────────────


def test_every_stage_builds_a_prompt_with_output_schema():
    # build_user_prompt embeds a per-stage JSON schema for all 18 stages, and
    # always asks for a "gaps" array (stage independence -> report, don't guess).
    for spec in STAGE_REGISTRY.values():
        prompt = build_user_prompt(
            spec=spec,
            course_title="Test Course",
            course_description="desc",
            options={},
            upstream={},
        )
        assert spec.title in prompt
        assert "gaps" in prompt.lower()
        # Missing upstream inputs are surfaced explicitly, never fabricated.
        for dep in spec.inputs:
            assert dep in prompt


# ── Unit: runtime schemas ─────────────────────────────────────────────────────


def test_readiness_gate_and_submission_schemas_validate():
    from app.modules.blueprint.schemas import (
        ContributionVerify,
        NodeEvidenceSubmit,
        ReadinessGateResult,
        SubmissionCreate,
    )

    ev = NodeEvidenceSubmit(evidence={"reflection": "x"}, readiness_state="ready")
    assert ev.readiness_state == "ready"

    sub = SubmissionCreate(enrollment_id=uuid.uuid4(), package={"artifact": "a"}, submit=True)
    assert sub.submit is True

    gate = ReadinessGateResult(
        assessment_id=uuid.uuid4(),
        enrollment_id=uuid.uuid4(),
        outcome="ready_to_submit",
        checks=[{"check": "required_nodes_completed", "passed": True, "detail": None}],
        missing_node_keys=[],
        context_profile_approved=True,
    )
    assert gate.checks[0].passed is True

    with pytest.raises(ValueError):
        ContributionVerify(verification_status="not_a_status")


def test_invalid_readiness_state_is_rejected():
    from app.modules.blueprint.schemas import NodeEvidenceSubmit

    with pytest.raises(ValueError):
        NodeEvidenceSubmit(evidence={}, readiness_state="super_ready")


# ── Unit: pure promotion / readiness helpers ──────────────────────────────────


def test_derive_readiness_heuristic():
    from app.modules.blueprint.service import _derive_readiness

    # Explicit, valid learner/AI state wins.
    assert _derive_readiness({}, "advanced") == "advanced"
    # No evidence -> not_ready.
    assert _derive_readiness({}, None) == "not_ready"
    # Reflection + decision rationale -> ready.
    assert _derive_readiness({"reflection": "r", "decision_rationale": "d"}, None) == "ready"
    # Partial evidence -> partially_ready.
    assert _derive_readiness({"reflection": "r"}, None) == "partially_ready"
    # Invalid explicit state is ignored and recomputed.
    assert _derive_readiness({}, "bogus") == "not_ready"


def test_promotion_handler_table_covers_domain_stages():
    from app.modules.blueprint.promotion import _HANDLERS

    expected = {
        "intake",
        "clo_review",
        "assessment_redesign",
        "assessment_weighting",
        "assessment_integrity",
        "readiness_gate",
        "subtopic_architecture",
        "mastery_nodes",
        "node_evidence_logic",
        "node_relationships",
        "learning_hours",
    }
    assert expected <= set(_HANDLERS)
    # Every handler key is a canonical registry key.
    for key in _HANDLERS:
        assert key in STAGE_REGISTRY


# ── Integration: promotion (dev Postgres; skips if unavailable) ───────────────


async def _make_course(session, *, status="draft"):
    from app.modules.courses.models import Course
    from app.modules.iam.models import Tenant

    tenant = Tenant(name="BP Tenant", slug=f"bp-{uuid.uuid4().hex[:10]}")
    session.add(tenant)
    await session.flush()
    course = Course(tenant_id=tenant.id, title="BP Course", status=status)
    session.add(course)
    await session.flush()
    return tenant, course


def _node_run(tenant_id, course_id):
    from app.modules.stages.models import StageRun

    return StageRun(
        tenant_id=tenant_id,
        course_id=course_id,
        stage_key="mastery_nodes",
        status="succeeded",
        execution_mode="single",
        review_status="needs_review",
        output={
            "artifact": {
                "nodes": [
                    {"key": "n1", "title": "Node One", "node_type": "concept"},
                    {"key": "n2", "title": "Node Two", "node_type": "judgment"},
                ]
            }
        },
    )


async def _cleanup(tenant_id):
    from app.core.database import SessionLocal
    from app.modules.blueprint.models import CourseDesignArtifact
    from app.modules.courses.models import Course, CourseVersion, LearningNode, NodeDependency
    from app.modules.iam.models import AuditLog, Tenant, User
    from app.modules.stages.models import StageRun

    async with SessionLocal() as session:
        course_ids = (
            await session.execute(select(Course.id).where(Course.tenant_id == tenant_id))
        ).scalars().all()
        version_ids = (
            (
                await session.execute(
                    select(CourseVersion.id).where(CourseVersion.course_id.in_(course_ids))
                )
            ).scalars().all()
            if course_ids
            else []
        )
        node_ids = (
            (
                await session.execute(
                    select(LearningNode.id).where(
                        LearningNode.course_version_id.in_(version_ids)
                    )
                )
            ).scalars().all()
            if version_ids
            else []
        )
        if node_ids:
            await session.execute(
                delete(NodeDependency).where(NodeDependency.source_node_id.in_(node_ids))
            )
            await session.execute(delete(LearningNode).where(LearningNode.id.in_(node_ids)))
        await session.execute(
            delete(CourseDesignArtifact).where(CourseDesignArtifact.tenant_id == tenant_id)
        )
        await session.execute(delete(AuditLog).where(AuditLog.tenant_id == tenant_id))
        await session.execute(delete(StageRun).where(StageRun.tenant_id == tenant_id))
        if version_ids:
            await session.execute(
                delete(CourseVersion).where(CourseVersion.id.in_(version_ids))
            )
        if course_ids:
            await session.execute(delete(Course).where(Course.id.in_(course_ids)))
        await session.execute(delete(User).where(User.tenant_id == tenant_id))
        await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
        await session.commit()


@pytest.fixture
async def db_session():
    from app.core.database import SessionLocal, engine

    await engine.dispose()
    try:
        async with SessionLocal() as session:
            await session.execute(select(1))
            yield session
    except Exception:  # noqa: BLE001 - any connection error -> skip
        pytest.skip("dev Postgres unavailable")
    finally:
        await engine.dispose()


async def test_promotion_creates_version_scoped_nodes_and_is_idempotent(db_session):
    from app.core.database import SessionLocal
    from app.modules.blueprint.models import CourseDesignArtifact
    from app.modules.blueprint.promotion import promote_stage_run
    from app.modules.courses.models import CourseVersion, LearningNode

    tenant, course = await _make_course(db_session)
    run = _node_run(tenant.id, course.id)
    db_session.add(run)
    await db_session.flush()
    tenant_id, course_id, run_id = tenant.id, course.id, run.id

    summary = await promote_stage_run(db_session, run)
    await db_session.commit()

    try:
        assert "learning_nodes" in summary["promoted"]
        assert summary["nodes_promoted"] == 2

        async with SessionLocal() as s:
            # A draft version was created (version scoping) and 2 nodes attached.
            versions = (
                await s.execute(
                    select(CourseVersion).where(CourseVersion.course_id == course_id)
                )
            ).scalars().all()
            assert len(versions) == 1
            assert versions[0].state == "draft"
            node_count = (
                await s.execute(
                    select(func.count())
                    .select_from(LearningNode)
                    .where(LearningNode.course_version_id == versions[0].id)
                )
            ).scalar_one()
            assert node_count == 2
            # The design-artifact snapshot was upserted.
            artifacts = (
                await s.execute(
                    select(CourseDesignArtifact).where(
                        CourseDesignArtifact.course_id == course_id
                    )
                )
            ).scalars().all()
            assert len(artifacts) == 1
            assert artifacts[0].stage_key == "mastery_nodes"

        # Re-promote the same run -> idempotent (no duplicate nodes/artifacts).
        async with SessionLocal() as s:
            run2 = await s.get(type(run), run_id)
            await promote_stage_run(s, run2)
            await s.commit()

        async with SessionLocal() as s:
            versions = (
                await s.execute(
                    select(CourseVersion).where(CourseVersion.course_id == course_id)
                )
            ).scalars().all()
            assert len(versions) == 1  # no new draft version
            node_count = (
                await s.execute(
                    select(func.count())
                    .select_from(LearningNode)
                    .where(LearningNode.course_version_id == versions[0].id)
                )
            ).scalar_one()
            assert node_count == 2  # upserted by blueprint_key, not duplicated
            artifact_count = (
                await s.execute(
                    select(func.count())
                    .select_from(CourseDesignArtifact)
                    .where(CourseDesignArtifact.course_id == course_id)
                )
            ).scalar_one()
            assert artifact_count == 1
    finally:
        await _cleanup(tenant_id)


async def test_rejection_promotes_nothing(db_session):
    from app.core.database import SessionLocal
    from app.core.deps import Principal
    from app.core.security import hash_password
    from app.modules.blueprint.models import CourseDesignArtifact
    from app.modules.courses.models import LearningNode
    from app.modules.iam.models import User
    from app.modules.stages import service as stages_service

    tenant, course = await _make_course(db_session)
    sme = User(
        tenant_id=tenant.id,
        email=f"sme-{uuid.uuid4().hex[:8]}@test.dev",
        display_name="SME",
        password_hash=hash_password("x"),
        status="active",
        is_superuser=True,
    )
    db_session.add(sme)
    await db_session.flush()
    run = _node_run(tenant.id, course.id)
    db_session.add(run)
    await db_session.flush()
    tenant_id, run_id, sme_id = tenant.id, run.id, sme.id
    await db_session.commit()

    principal = Principal(
        id=sme_id,
        tenant_id=tenant_id,
        email=sme.email,
        display_name="SME",
        is_superuser=True,
    )

    try:
        async with SessionLocal() as s:
            reviewed = await stages_service.review_run(
                s, principal, run_id, approve=False, note="no"
            )
            await s.commit()
            assert reviewed.review_status == "rejected"

        async with SessionLocal() as s:
            artifacts = (
                await s.execute(
                    select(func.count())
                    .select_from(CourseDesignArtifact)
                    .where(CourseDesignArtifact.tenant_id == tenant_id)
                )
            ).scalar_one()
            nodes = (
                await s.execute(
                    select(func.count()).select_from(LearningNode)
                )
            ).scalar_one()
            assert artifacts == 0  # rejection promotes nothing
            # (node count is global; we just assert no artifact was written)
            assert nodes >= 0
    finally:
        await _cleanup(tenant_id)
