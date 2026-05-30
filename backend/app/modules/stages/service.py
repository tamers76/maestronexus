"""Stage service: run stages as independent features, with council + governance.

Business logic lives here so the router stays a thin HTTP shell. ``run_stage`` is
deliberately *independent*: it gathers whatever upstream artifacts exist and
proceeds, recording missing inputs as gaps rather than blocking. Each run is
persisted as a :class:`StageRun`, scored for risk, routed for SME review when
needed, audited, and (for deep stages) promoted into the domain.
"""

from __future__ import annotations

import json
import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.deps import Principal, ensure_same_tenant
from app.modules.ai import council
from app.modules.courses import service as courses_service
from app.modules.integrations import service as settings_service
from app.modules.stages import extraction
from app.modules.stages.definitions import (
    STAGE_REGISTRY,
    aliases_for,
    canonical_key,
    get_stage,
    ordered_stages,
    stage_key_variants,
)
from app.modules.stages.models import StageRun
from app.modules.stages.prompts import build_user_prompt
from app.modules.stages.schemas import RunStageRequest


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


# ── Reads ───────────────────────────────────────────────────────────────────


async def _latest_succeeded(
    session: AsyncSession, course_id: uuid.UUID, stage_key: str
) -> StageRun | None:
    return (
        await session.execute(
            select(StageRun)
            .where(
                StageRun.course_id == course_id,
                StageRun.stage_key.in_(stage_key_variants(stage_key)),
                StageRun.status == "succeeded",
            )
            .order_by(StageRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _latest_any(
    session: AsyncSession, course_id: uuid.UUID, stage_key: str
) -> StageRun | None:
    return (
        await session.execute(
            select(StageRun)
            .where(
                StageRun.course_id == course_id,
                StageRun.stage_key.in_(stage_key_variants(stage_key)),
            )
            .order_by(StageRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def list_course_stages(
    session: AsyncSession, user: Principal, course_id: uuid.UUID
) -> list[dict]:
    """Catalog + latest run per stage for a course (the Studio board)."""

    await courses_service.load_course(session, user, course_id)
    out: list[dict] = []
    for spec in ordered_stages():
        last = await _latest_any(session, course_id, spec.key)
        out.append(
            {
                "key": spec.key,
                "order": spec.order,
                "title": spec.title,
                "description": spec.description,
                "risk": spec.risk,
                "default_execution": spec.default_execution,
                "promotes_to": spec.promotes_to,
                "aliases": aliases_for(spec.key),
                "last_run": last,
            }
        )
    return out


async def load_run(session: AsyncSession, user: Principal, run_id: uuid.UUID) -> StageRun:
    run = await session.get(StageRun, run_id)
    if run is None:
        raise _not_found("Stage run")
    ensure_same_tenant(user, run.tenant_id)
    return run


async def list_runs(
    session: AsyncSession, user: Principal, course_id: uuid.UUID, stage_key: str | None
) -> list[StageRun]:
    await courses_service.load_course(session, user, course_id)
    stmt = select(StageRun).where(StageRun.course_id == course_id)
    if stage_key:
        stmt = stmt.where(StageRun.stage_key.in_(stage_key_variants(stage_key)))
    rows = (
        (await session.execute(stmt.order_by(StageRun.created_at.desc()))).scalars().all()
    )
    return list(rows)


# ── Run ─────────────────────────────────────────────────────────────────────


_CODE_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_SMART_DOUBLE = re.compile(r"[\u201c\u201d\u201e\u201f\u2033\u2036]")
_SMART_SINGLE = re.compile(r"[\u2018\u2019\u201a\u201b\u2032\u2035]")
_DASHES = re.compile(r"[\u2013\u2014]")
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def parse_ai_json(text: str) -> dict | list | None:
    """Robustly parse a JSON object/array out of an LLM response.

    Ported from DeepT's ``parseAIJson`` (``ai.service.ts``): strips ```json
    fences, skips explanatory preamble to the first ``{``/``[``, slices to the
    matching closing bracket, normalizes smart quotes/dashes, and retries after
    removing trailing commas. Returns ``None`` when no JSON can be recovered
    (callers degrade gracefully rather than raising).
    """

    if not text:
        return None
    cleaned = text.strip()

    fence = _CODE_FENCE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()

    # Skip any leading prose: jump to the first JSON opener.
    start = next((i for i, ch in enumerate(cleaned) if ch in "{["), -1)
    if start == -1:
        return None
    cleaned = cleaned[start:]

    # Slice to the matching closing bracket (string/escape aware) so trailing
    # commentary (e.g. a chairman "SME Summary:") doesn't break parsing.
    end = _matching_bracket_end(cleaned)
    if end != -1:
        cleaned = cleaned[: end + 1]

    cleaned = _SMART_DOUBLE.sub('"', cleaned)
    cleaned = _SMART_SINGLE.sub("'", cleaned)
    cleaned = _DASHES.sub("-", cleaned)

    try:
        return json.loads(cleaned)
    except Exception:
        pass
    try:
        return json.loads(_TRAILING_COMMA.sub(r"\1", cleaned))
    except Exception:
        return None


def _matching_bracket_end(text: str) -> int:
    """Index of the bracket that closes ``text[0]``, or -1 if unbalanced."""

    opener = text[0]
    if opener not in "{[":
        return -1
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _parse_artifact(text: str) -> tuple[dict | list | None, list]:
    """Best-effort JSON parse of a stage answer; extract a ``gaps`` list."""

    parsed = parse_ai_json(text)
    gaps = parsed.get("gaps", []) if isinstance(parsed, dict) else []
    return parsed, gaps if isinstance(gaps, list) else []


def _artifact_has_clos(artifact: object) -> bool:
    """True when ``artifact`` already carries at least one usable CLO."""

    if not isinstance(artifact, dict):
        return False
    raw = (
        artifact.get("clos")
        or artifact.get("course_learning_outcomes")
        or artifact.get("learning_outcomes")
        or []
    )
    if not isinstance(raw, list):
        return False
    for item in raw:
        if isinstance(item, str) and item.strip():
            return True
        if isinstance(item, dict) and any(
            str(item.get(k, "")).strip() for k in ("statement", "clo_text", "text", "outcome")
        ):
            return True
    return False


def _finalize_intake_artifact(
    parsed: dict | list | None, gaps: list, syllabus_text: str | None, course
) -> tuple[dict, list]:
    """Guarantee the intake artifact carries a ``clos`` array (DeepT Stage 1).

    If the model returned usable CLOs we keep them untouched. Otherwise — the
    common offline/stub case, where the response isn't valid JSON — we fall back
    to a deterministic extraction of the syllabus text so CLOs that are present
    in the source still land on the course.
    """

    artifact = dict(parsed) if isinstance(parsed, dict) else {}
    if _artifact_has_clos(artifact):
        return artifact, gaps

    contract = extraction.extract_course_contract(str(syllabus_text or ""), title=course.title)
    # Keep any real model-provided metadata; fill blanks from the heuristic.
    merged = {**{k: v for k, v in contract.items() if v}, **artifact}
    if contract.get("clos"):
        merged["clos"] = contract["clos"]

    new_gaps = list(gaps)
    if not _artifact_has_clos(merged):
        note = "No Course Learning Outcomes found in the syllabus text."
        if note not in new_gaps:
            new_gaps.append(note)
    merged["gaps"] = new_gaps
    return merged, new_gaps


def _compute_risk(spec, *, stubbed: bool, gaps: list) -> float:
    score = 0.7 if spec.risk == "high" else 0.3
    if gaps:
        score += 0.1
    if stubbed:
        score += 0.1
    return round(min(score, 1.0), 2)


async def _gather_upstream(
    session: AsyncSession, course_id: uuid.UUID, spec
) -> tuple[dict, dict]:
    """Collect available upstream artifacts. Returns (outputs, run_id_refs)."""

    outputs: dict = {}
    refs: dict = {}
    for dep in spec.inputs:
        run = await _latest_succeeded(session, course_id, dep)
        if run is not None:
            outputs[dep] = run.output.get("artifact") or run.output.get("text")
            refs[dep] = str(run.id)
    return outputs, refs


async def run_stage(
    session: AsyncSession,
    user: Principal,
    course_id: uuid.UUID,
    stage_key: str,
    req: RunStageRequest,
) -> StageRun:
    course = await courses_service.load_course(session, user, course_id)
    spec = get_stage(stage_key)
    if spec is None:
        raise _not_found("Stage")
    # Canonicalize legacy keys (e.g. clo_refinement -> clo_review) so new runs
    # are stored under the Blueprint's canonical stage_key.
    stage_key = spec.key

    resolved = await settings_service.resolve_stage_execution(
        session, user.tenant_id, stage_key, mode_override=req.mode
    )

    options = dict(req.options or {})
    # Deep stage: Course Intake pulls syllabus text from storage if referenced.
    if spec.key == "intake" and not options.get("syllabus_text"):
        storage_key = options.get("storage_key")
        if storage_key:
            try:
                options["syllabus_text"] = extraction.fetch_storage_text(str(storage_key))
            except Exception as exc:  # storage unavailable -> proceed, note gap
                options["syllabus_extraction_error"] = str(exc)

    upstream, upstream_refs = await _gather_upstream(session, course_id, spec)
    user_prompt = build_user_prompt(
        spec=spec,
        course_title=course.title,
        course_description=course.description,
        options=options,
        upstream=upstream,
    )

    input_refs = {
        "mode": resolved.mode,
        "upstream_runs": upstream_refs,
        "options": {k: v for k, v in options.items() if k != "syllabus_text"},
        "models": {
            "single": resolved.single_model,
            "council": resolved.council_models,
            "chairman": resolved.chairman_model,
        },
    }

    run = StageRun(
        tenant_id=user.tenant_id,
        created_by=user.id,
        course_id=course_id,
        course_version_id=req.course_version_id,
        stage_key=stage_key,
        status="running",
        execution_mode=resolved.mode,
        input_refs=input_refs,
        output={},
        council_transcript={},
    )
    session.add(run)
    await session.flush()

    try:
        if resolved.mode == "council":
            result = await council.run_council(
                user=user_prompt,
                members=resolved.council_models,
                chairman=resolved.chairman_model,
                member_system_prompt=resolved.member_system_prompt,
                chairman_system_prompt=resolved.chairman_system_prompt,
                provider_key=resolved.provider,
                api_key=resolved.api_key,
                base_url=resolved.base_url,
            )
        else:
            result = await council.run_single(
                system=resolved.member_system_prompt,
                user=user_prompt,
                model=resolved.single_model,
                provider_key=resolved.provider,
                api_key=resolved.api_key,
                base_url=resolved.base_url,
            )
    except Exception as exc:  # pragma: no cover - defensive
        run.status = "failed"
        run.output = {"error": str(exc)}
        run.review_status = "auto_ok"
        await session.flush()
        await record_audit(
            session,
            tenant_id=user.tenant_id,
            actor_id=user.id,
            action="stage.run.failed",
            object_type="stage_run",
            object_id=run.id,
            metadata={"stage_key": stage_key, "error": str(exc)},
        )
        return run

    parsed, gaps = _parse_artifact(result.text)
    # Course Intake must always yield a CLO array; fall back to deterministic
    # syllabus extraction when the model (or offline stub) didn't return one.
    if spec.key == "intake":
        parsed, gaps = _finalize_intake_artifact(
            parsed, gaps, options.get("syllabus_text"), course
        )
    run.status = "succeeded"
    run.output = {
        "text": result.text,
        "artifact": parsed,
        "gaps": gaps,
        "stubbed": result.stubbed,
        "output_kind": spec.output_kind,
    }
    run.council_transcript = result.transcript()
    run.risk_score = _compute_risk(spec, stubbed=result.stubbed, gaps=gaps)
    run.review_status = "needs_review" if spec.risk == "high" else "auto_ok"
    await session.flush()

    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="stage.run",
        object_type="stage_run",
        object_id=run.id,
        metadata={
            "stage_key": stage_key,
            "mode": resolved.mode,
            "stubbed": result.stubbed,
            "risk_score": run.risk_score,
            "review_status": run.review_status,
        },
    )
    return run


# ── Governance (SME review) ───────────────────────────────────────────────────


async def review_run(
    session: AsyncSession,
    user: Principal,
    run_id: uuid.UUID,
    *,
    approve: bool,
    note: str | None,
) -> StageRun:
    run = await load_run(session, user, run_id)
    run.review_status = "approved" if approve else "rejected"
    await session.flush()

    # Promotion happens only on approval (rejection promotes nothing). Stage
    # artifacts are promoted into approved domain state by the blueprint module.
    promotion_summary: dict | None = None
    if approve:
        # Lazy import avoids a stages<->blueprint import cycle.
        from app.modules.blueprint import promotion

        promotion_summary = await promotion.promote_stage_run(session, run)

    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="stage.run.approve" if approve else "stage.run.reject",
        object_type="stage_run",
        object_id=run.id,
        metadata={
            "note": note,
            "promotion": promotion_summary,
        }
        if (note or promotion_summary)
        else None,
    )
    return run


def catalog() -> list[dict]:
    return [
        {
            "key": s.key,
            "order": s.order,
            "title": s.title,
            "description": s.description,
            "inputs": s.inputs,
            "output_kind": s.output_kind,
            "default_execution": s.default_execution,
            "risk": s.risk,
            "promotes_to": s.promotes_to,
            "aliases": aliases_for(s.key),
        }
        for s in ordered_stages()
    ]


async def approved_artifact(
    session: AsyncSession, user: Principal, course_id: uuid.UUID, stage_key: str
) -> dict | None:
    """The current approved design artifact for a stage on a course (or None).

    Looks up the promoted :class:`CourseDesignArtifact` snapshot; falls back to
    the latest approved ``StageRun`` artifact when no snapshot exists yet.
    """

    await courses_service.load_course(session, user, course_id)
    canon = canonical_key(stage_key)

    from app.modules.blueprint.models import CourseDesignArtifact

    snapshot = (
        await session.execute(
            select(CourseDesignArtifact)
            .where(
                CourseDesignArtifact.course_id == course_id,
                CourseDesignArtifact.stage_key == canon,
            )
            .order_by(CourseDesignArtifact.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if snapshot is not None:
        return {
            "source": "design_artifact",
            "stage_key": canon,
            "review_status": snapshot.review_status,
            "course_version_id": (
                str(snapshot.course_version_id) if snapshot.course_version_id else None
            ),
            "source_run_id": str(snapshot.source_run_id) if snapshot.source_run_id else None,
            "artifact": snapshot.artifact,
            "updated_at": snapshot.updated_at.isoformat(),
        }

    run = (
        await session.execute(
            select(StageRun)
            .where(
                StageRun.course_id == course_id,
                StageRun.stage_key.in_(stage_key_variants(canon)),
                StageRun.review_status == "approved",
            )
            .order_by(StageRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run is None:
        return None
    return {
        "source": "stage_run",
        "stage_key": canon,
        "review_status": run.review_status,
        "course_version_id": str(run.course_version_id) if run.course_version_id else None,
        "source_run_id": str(run.id),
        "artifact": (run.output or {}).get("artifact"),
        "updated_at": run.created_at.isoformat(),
    }


__all__ = [
    "list_course_stages",
    "load_run",
    "list_runs",
    "run_stage",
    "review_run",
    "catalog",
    "approved_artifact",
    "parse_ai_json",
    "STAGE_REGISTRY",
]
