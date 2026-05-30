"""Approval-time promotion: structured stage artifacts -> approved domain state.

Called from ``stages.service.review_run`` only when an SME *approves* a run
(rejection promotes nothing). Every approval upserts a ``CourseDesignArtifact``
snapshot; stages that map onto concrete domain rows (CLOs, subtopics,
contribution assessments, nodes, edges, effort maps) also promote those.

Promotion is **idempotent**: re-approving the same (or a newer) run for a stage
upserts by stable identifiers instead of inserting duplicates, and is **version
scoped** to ``StageRun.course_version_id`` (falling back to the course's latest
draft version for graph promotions).
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.courses import service as courses_service
from app.modules.courses.models import (
    CourseVersion,
    LearningNode,
    LearningOutcome,
    NodeDependency,
)
from app.modules.stages.definitions import canonical_key
from app.modules.stages.models import StageRun

# Blueprint relationship type -> learning-graph dependency_type. Prerequisite/
# dependency edges gate availability (``requires``); the rest are stored verbatim
# for adaptivity/diagnosis without locking the graph.
_RELATIONSHIP_TO_DEP = {
    "prerequisite": "requires",
    "dependency": "requires",
}


def _slug(value: str, *, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return s[:120] or fallback


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


# ── Snapshot ──────────────────────────────────────────────────────────────────


async def _upsert_design_artifact(
    session: AsyncSession, run: StageRun, stage_key: str, artifact: object
) -> None:
    from app.modules.blueprint.models import CourseDesignArtifact

    existing = (
        await session.execute(
            select(CourseDesignArtifact).where(
                CourseDesignArtifact.course_id == run.course_id,
                CourseDesignArtifact.course_version_id == run.course_version_id,
                CourseDesignArtifact.stage_key == stage_key,
            )
        )
    ).scalar_one_or_none()
    payload = artifact if isinstance(artifact, dict | list) else {}
    if existing is None:
        session.add(
            CourseDesignArtifact(
                tenant_id=run.tenant_id,
                created_by=run.created_by,
                course_id=run.course_id,
                course_version_id=run.course_version_id,
                stage_key=stage_key,
                source_run_id=run.id,
                review_status="approved",
                artifact=payload if isinstance(payload, dict) else {"items": payload},
            )
        )
    else:
        existing.source_run_id = run.id
        existing.review_status = "approved"
        existing.artifact = payload if isinstance(payload, dict) else {"items": payload}
    await session.flush()


# ── Version helper ─────────────────────────────────────────────────────────────


async def _ensure_draft_version(session: AsyncSession, run: StageRun) -> CourseVersion:
    if run.course_version_id is not None:
        version = await session.get(CourseVersion, run.course_version_id)
        if version is not None:
            return version
    latest = (
        await session.execute(
            select(CourseVersion)
            .where(CourseVersion.course_id == run.course_id)
            .order_by(CourseVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest is not None and latest.state != "published":
        return latest
    version = CourseVersion(
        course_id=run.course_id,
        version=(latest.version + 1) if latest else 1,
        state="draft",
        created_by=run.created_by,
    )
    session.add(version)
    await session.flush()
    return version


async def _nodes_by_blueprint_key(
    session: AsyncSession, version_id: uuid.UUID
) -> dict[str, LearningNode]:
    rows = (
        (
            await session.execute(
                select(LearningNode).where(LearningNode.course_version_id == version_id)
            )
        )
        .scalars()
        .all()
    )
    out: dict[str, LearningNode] = {}
    for node in rows:
        key = (node.node_metadata or {}).get("blueprint_key")
        if key:
            out[str(key)] = node
    return out


# ── Domain handlers ─────────────────────────────────────────────────────────────


async def _promote_intake(session: AsyncSession, run: StageRun, artifact: dict) -> dict:
    inserted = await courses_service.promote_intake(
        session, tenant_id=run.tenant_id, course_id=run.course_id, artifact=artifact
    )
    return {"clos_inserted": inserted, "promoted": ["course_metadata", "clos"]}


async def _promote_clo_review(session: AsyncSession, run: StageRun, artifact: dict) -> dict:
    refined = artifact.get("clos") or artifact.get("refined_clos") or []
    await courses_service.apply_refined_clos(
        session, tenant_id=run.tenant_id, course_id=run.course_id, refined=refined
    )
    return {"clos_refined": len(_as_list(refined)), "promoted": ["learning_outcomes"]}


async def _get_or_create_assessment(
    session: AsyncSession, run: StageRun, key: str, title: str
):
    from app.modules.blueprint.models import ContributionAssessment

    row = (
        await session.execute(
            select(ContributionAssessment).where(
                ContributionAssessment.course_id == run.course_id,
                ContributionAssessment.assessment_key == key,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = ContributionAssessment(
            tenant_id=run.tenant_id,
            created_by=run.created_by,
            course_id=run.course_id,
            course_version_id=run.course_version_id,
            assessment_key=key,
            title=title or key,
            status="approved",
        )
        session.add(row)
    row.source_run_id = run.id
    row.status = "approved"
    return row


async def _promote_assessments(session: AsyncSession, run: StageRun, artifact: dict) -> dict:
    """assessment_redesign / assessment_weighting / assessment_integrity."""

    items = _as_list(artifact.get("assessments"))
    stage = canonical_key(run.stage_key)
    count = 0
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("original_title") or "").strip()
        key = str(item.get("key") or "").strip() or _slug(title, fallback=f"assessment-{index + 1}")
        row = await _get_or_create_assessment(session, run, key, title)
        row.position = index

        if stage == "assessment_redesign":
            if title:
                row.title = title[:512]
            row.original_title = (item.get("original_title") or row.original_title)
            row.contribution_purpose = item.get("contribution_purpose")
            row.clo_codes = _as_list(item.get("clo_codes"))
            core = item.get("fixed_core")
            row.fixed_core = core if isinstance(core, dict) else {}
            row.personalized_variables = _as_list(item.get("personalized_variables"))
            row.required_artifact = item.get("required_artifact")
            row.output_formats = _as_list(item.get("output_formats"))
            row.publication_potential = item.get("publication_potential")
            criteria = _as_list(item.get("rubric_criteria"))
            if criteria:
                rubric = dict(row.rubric or {})
                rubric["criteria"] = criteria
                row.rubric = rubric
            if item.get("ai_integrity_features"):
                req = dict(row.integrity_requirements or {})
                req["features"] = _as_list(item.get("ai_integrity_features"))
                row.integrity_requirements = req
            if item.get("readiness_gate_needs"):
                gate = dict(row.readiness_gate or {})
                gate["needs"] = _as_list(item.get("readiness_gate_needs"))
                row.readiness_gate = gate
        elif stage == "assessment_weighting":
            weight = item.get("proposed_weight")
            if weight is None:
                weight = item.get("current_weight")
            if isinstance(weight, int | float):
                row.weight = float(weight)
            rubric = dict(row.rubric or {})
            if item.get("rubric"):
                rubric["weighted_criteria"] = _as_list(item.get("rubric"))
            if item.get("grading_policy"):
                rubric["grading_policy"] = item.get("grading_policy")
            if item.get("revision_policy"):
                rubric["revision_policy"] = item.get("revision_policy")
            if item.get("required_process_evidence"):
                rubric["required_process_evidence"] = _as_list(
                    item.get("required_process_evidence")
                )
            row.rubric = rubric
            if item.get("clo_codes") and not row.clo_codes:
                row.clo_codes = _as_list(item.get("clo_codes"))
        elif stage == "assessment_integrity":
            req = dict(row.integrity_requirements or {})
            for field in (
                "required_process",
                "integrity_layers",
                "ai_use_disclosure_fields",
                "passive_ai_risks",
                "recommended_changes",
            ):
                if item.get(field) is not None:
                    req[field] = _as_list(item.get(field))
            row.integrity_requirements = req
        count += 1
    await session.flush()
    return {"assessments_promoted": count, "promoted": ["contribution_assessments"]}


async def _promote_readiness_gates(session: AsyncSession, run: StageRun, artifact: dict) -> dict:
    gates = _as_list(artifact.get("gates"))
    count = 0
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        key = str(gate.get("assessment_key") or "").strip()
        if not key:
            continue
        from app.modules.blueprint.models import ContributionAssessment

        row = (
            await session.execute(
                select(ContributionAssessment).where(
                    ContributionAssessment.course_id == run.course_id,
                    ContributionAssessment.assessment_key == key,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = await _get_or_create_assessment(session, run, key, key)
        merged = dict(row.readiness_gate or {})
        merged["required_node_keys"] = _as_list(gate.get("required_node_keys"))
        merged["checks"] = _as_list(gate.get("checks"))
        merged["outcomes"] = _as_list(gate.get("outcomes"))
        row.readiness_gate = merged
        count += 1
    await session.flush()
    return {"gates_promoted": count, "promoted": ["contribution_assessments"]}


async def _promote_subtopics(session: AsyncSession, run: StageRun, artifact: dict) -> dict:
    from app.modules.blueprint.models import CourseSubtopic

    items = _as_list(artifact.get("subtopics"))
    clo_rows = (
        (
            await session.execute(
                select(LearningOutcome).where(LearningOutcome.course_id == run.course_id)
            )
        )
        .scalars()
        .all()
    )
    outcome_by_code = {r.code: r.id for r in clo_rows if r.code}
    count = 0
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        key = str(item.get("key") or "").strip() or _slug(title, fallback=f"subtopic-{index + 1}")
        row = (
            await session.execute(
                select(CourseSubtopic).where(
                    CourseSubtopic.course_id == run.course_id,
                    CourseSubtopic.subtopic_key == key,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = CourseSubtopic(
                tenant_id=run.tenant_id,
                created_by=run.created_by,
                course_id=run.course_id,
                course_version_id=run.course_version_id,
                subtopic_key=key,
                title=title or key,
            )
            session.add(row)
        row.title = (title or key)[:512]
        row.clo_code = item.get("clo_code")
        row.outcome_id = outcome_by_code.get(item.get("clo_code"))
        row.purpose = item.get("purpose")
        row.learning_function = item.get("learning_function")
        row.position = index
        row.source_run_id = run.id
        row.attributes = {
            k: v
            for k, v in item.items()
            if k not in {"key", "title", "clo_code", "purpose", "learning_function"}
        }
        count += 1
    await session.flush()
    return {"subtopics_promoted": count, "promoted": ["course_subtopics"]}


async def _promote_nodes(session: AsyncSession, run: StageRun, artifact: dict) -> dict:
    version = await _ensure_draft_version(session, run)
    existing = await _nodes_by_blueprint_key(session, version.id)
    items = _as_list(artifact.get("nodes"))
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        key = str(item.get("key") or "").strip() or _slug(title, fallback=f"node-{count + 1}")
        node = existing.get(key)
        learning_objective = {
            "mastery_statement": item.get("mastery_statement"),
            "clo_code": item.get("clo_code"),
            "why_it_matters": item.get("why_it_matters"),
            "assessment_connection": item.get("assessment_connection"),
        }
        metadata = {
            "blueprint_key": key,
            "subtopic_key": item.get("subtopic_key"),
            "node_type_label": item.get("node_type"),
            "ai_companion_guidance": item.get("ai_companion_guidance"),
            "misconceptions": _as_list(item.get("misconceptions")),
            "prerequisites": _as_list(item.get("prerequisites")),
            "dependencies": _as_list(item.get("dependencies")),
        }
        duration = item.get("estimated_duration_minutes")
        duration = int(duration) if isinstance(duration, int | float) else None
        if node is None:
            node = LearningNode(
                course_version_id=version.id,
                type=str(item.get("node_type") or "mastery_node")[:48],
                title=(title or key)[:255],
                learning_objective=learning_objective,
                estimated_duration=duration,
                node_metadata=metadata,
            )
            session.add(node)
            existing[key] = node
        else:
            node.title = (title or key)[:255]
            node.type = str(item.get("node_type") or node.type)[:48]
            node.learning_objective = learning_objective
            if duration is not None:
                node.estimated_duration = duration
            merged_meta = dict(node.node_metadata or {})
            merged_meta.update(metadata)
            node.node_metadata = merged_meta
        count += 1
    await session.flush()
    return {
        "nodes_promoted": count,
        "course_version_id": str(version.id),
        "promoted": ["learning_nodes"],
    }


async def _promote_node_evidence_logic(
    session: AsyncSession, run: StageRun, artifact: dict
) -> dict:
    version = await _ensure_draft_version(session, run)
    existing = await _nodes_by_blueprint_key(session, version.id)
    count = 0
    for item in _as_list(artifact.get("nodes")):
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        node = existing.get(key)
        if node is None:
            continue
        node.mastery_rule = {
            "sufficient_evidence": item.get("sufficient_evidence"),
            "ready_indicators": _as_list(item.get("ready_indicators")),
            "advanced_indicators": _as_list(item.get("advanced_indicators")),
        }
        node.completion_rule = {
            "evidence_task": item.get("evidence_task"),
            "not_ready_indicators": _as_list(item.get("not_ready_indicators")),
            "partially_ready_indicators": _as_list(item.get("partially_ready_indicators")),
            "adaptive_actions": item.get("adaptive_actions")
            if isinstance(item.get("adaptive_actions"), dict)
            else {},
        }
        meta = dict(node.node_metadata or {})
        meta["node_role"] = item.get("node_role")
        meta["feedback_message"] = item.get("feedback_message")
        node.node_metadata = meta
        count += 1
    await session.flush()
    return {"nodes_updated": count, "promoted": ["node_evidence_rules"]}


async def _promote_relationships(session: AsyncSession, run: StageRun, artifact: dict) -> dict:
    version = await _ensure_draft_version(session, run)
    by_key = await _nodes_by_blueprint_key(session, version.id)
    node_ids = [n.id for n in by_key.values()]
    existing_edges: set[tuple[uuid.UUID, uuid.UUID, str]] = set()
    if node_ids:
        edges = (
            (
                await session.execute(
                    select(NodeDependency).where(NodeDependency.source_node_id.in_(node_ids))
                )
            )
            .scalars()
            .all()
        )
        existing_edges = {
            (e.source_node_id, e.target_node_id, e.dependency_type) for e in edges
        }
    count = 0
    for rel in _as_list(artifact.get("relationships")):
        if not isinstance(rel, dict):
            continue
        src = by_key.get(str(rel.get("source_key") or ""))
        tgt = by_key.get(str(rel.get("target_key") or ""))
        if src is None or tgt is None or src.id == tgt.id:
            continue
        rel_type = str(rel.get("relationship_type") or "prerequisite")
        dep_type = _RELATIONSHIP_TO_DEP.get(rel_type, rel_type)[:32]
        triple = (src.id, tgt.id, dep_type)
        if triple in existing_edges:
            continue
        # Skip an edge whose reverse already exists to avoid trivial cycles.
        if (tgt.id, src.id, dep_type) in existing_edges:
            continue
        session.add(
            NodeDependency(
                source_node_id=src.id, target_node_id=tgt.id, dependency_type=dep_type
            )
        )
        existing_edges.add(triple)
        count += 1
    await session.flush()
    return {"edges_promoted": count, "promoted": ["node_dependencies"]}


async def _promote_effort_map(session: AsyncSession, run: StageRun, artifact: dict) -> dict:
    from app.modules.blueprint.models import LearningEffortMap

    row = (
        await session.execute(
            select(LearningEffortMap).where(
                LearningEffortMap.course_id == run.course_id,
                LearningEffortMap.course_version_id == run.course_version_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = LearningEffortMap(
            tenant_id=run.tenant_id,
            created_by=run.created_by,
            course_id=run.course_id,
            course_version_id=run.course_version_id,
        )
        session.add(row)
    total = artifact.get("total_estimated_hours")
    row.total_estimated_hours = float(total) if isinstance(total, int | float) else None
    components = artifact.get("breakdown")
    row.breakdown = {
        "by_clo": _as_list(artifact.get("by_clo")),
        "components": components if isinstance(components, dict) else {},
    }
    row.accreditation_alignment = artifact.get("accreditation_alignment")
    row.source_run_id = run.id
    await session.flush()
    return {"promoted": ["learning_effort_map"]}


_HANDLERS = {
    "intake": _promote_intake,
    "clo_review": _promote_clo_review,
    "assessment_redesign": _promote_assessments,
    "assessment_weighting": _promote_assessments,
    "assessment_integrity": _promote_assessments,
    "readiness_gate": _promote_readiness_gates,
    "subtopic_architecture": _promote_subtopics,
    "mastery_nodes": _promote_nodes,
    "node_evidence_logic": _promote_node_evidence_logic,
    "node_relationships": _promote_relationships,
    "learning_hours": _promote_effort_map,
}


async def promote_stage_run(session: AsyncSession, run: StageRun) -> dict:
    """Promote an approved ``StageRun`` into approved domain state.

    Always upserts the stage's :class:`CourseDesignArtifact` snapshot; dispatches
    to a domain handler when the stage maps onto concrete rows. Returns a summary
    dict recorded in the approval audit log.
    """

    canon = canonical_key(run.stage_key)
    artifact = (run.output or {}).get("artifact")
    await _upsert_design_artifact(session, run, canon, artifact)

    summary: dict = {"stage_key": canon, "promoted": ["design_artifact"]}
    handler = _HANDLERS.get(canon)
    if handler is not None and isinstance(artifact, dict):
        result = await handler(session, run, artifact)
        summary["promoted"] = ["design_artifact", *result.pop("promoted", [])]
        summary.update(result)
    return summary


__all__ = ["promote_stage_run"]
