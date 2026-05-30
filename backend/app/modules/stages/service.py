"""Stage service: run stages as independent features, with council + governance.

Business logic lives here so the router stays a thin HTTP shell. ``run_stage`` is
deliberately *independent*: it gathers whatever upstream artifacts exist and
proceeds, recording missing inputs as gaps rather than blocking. Each run is
persisted as a :class:`StageRun`, scored for risk, routed for SME review when
needed, audited, and (for deep stages) promoted into the domain.
"""

from __future__ import annotations

import json
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.deps import Principal, ensure_same_tenant
from app.modules.ai import council
from app.modules.ai.models import AIGeneratedContent, AIInteraction
from app.modules.courses import service as courses_service
from app.modules.integrations import service as settings_service
from app.modules.stages import extraction
from app.modules.stages.definitions import STAGE_REGISTRY, get_stage, ordered_stages
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
                StageRun.stage_key == stage_key,
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
            .where(StageRun.course_id == course_id, StageRun.stage_key == stage_key)
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
        stmt = stmt.where(StageRun.stage_key == stage_key)
    rows = (
        (await session.execute(stmt.order_by(StageRun.created_at.desc()))).scalars().all()
    )
    return list(rows)


# ── Run ─────────────────────────────────────────────────────────────────────


def _parse_artifact(text: str) -> tuple[dict | list | None, list]:
    """Best-effort JSON parse of a stage answer; extract a ``gaps`` list."""

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        parsed = json.loads(cleaned)
    except Exception:
        return None, []
    gaps = parsed.get("gaps", []) if isinstance(parsed, dict) else []
    return parsed, gaps if isinstance(gaps, list) else []


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

    # Deep stage: Content Production lands in the human content-review flow.
    if spec.key == "content_production":
        await _promote_content_draft(session, user, run, result.text)

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


async def _promote_content_draft(
    session: AsyncSession, user: Principal, run: StageRun, text: str
) -> None:
    """Promote content-production output into the AI content review queue."""

    interaction = AIInteraction(
        tenant_id=user.tenant_id,
        user_id=user.id,
        agent="stage_content_production",
        context_refs={"stage_run_id": str(run.id), "course_id": str(run.course_id)},
        messages={"messages": [{"role": "assistant", "content": text}]},
    )
    session.add(interaction)
    await session.flush()
    draft = AIGeneratedContent(
        interaction_id=interaction.id,
        target_type="content_item",
        review_status="pending",
        draft={
            "format": "markdown",
            "body": text,
            "source": "stage:content_production",
            "stage_run_id": str(run.id),
        },
    )
    session.add(draft)
    await session.flush()
    refs = dict(run.input_refs)
    refs["content_draft_id"] = str(draft.id)
    run.input_refs = refs
    await session.flush()


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
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="stage.run.approve" if approve else "stage.run.reject",
        object_type="stage_run",
        object_id=run.id,
        metadata={"note": note} if note else None,
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
        }
        for s in ordered_stages()
    ]


__all__ = [
    "list_course_stages",
    "load_run",
    "list_runs",
    "run_stage",
    "review_run",
    "catalog",
    "STAGE_REGISTRY",
]
