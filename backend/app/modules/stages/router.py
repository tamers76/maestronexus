"""Stages module HTTP surface (docs/13).

Routes are thin: authenticate + authorize, delegate to the service, then commit.
Stage running requires ``stage.run``; SME approval/rejection requires
``stage.review`` (docx §10 governance).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import Principal, SessionDep, require_permission
from app.modules.stages import service
from app.modules.stages.schemas import (
    ReviewRequest,
    RunStageRequest,
    StageCatalogItem,
    StageRunOut,
    StageRunSummary,
    StageStatus,
)

router = APIRouter(prefix="/stages", tags=["stages"])

StageRunner = Annotated[Principal, Depends(require_permission("stage.run"))]
StageReviewer = Annotated[Principal, Depends(require_permission("stage.review"))]


def _run_summary(run) -> StageRunSummary | None:
    if run is None:
        return None
    return StageRunSummary(
        id=run.id,
        status=run.status,
        execution_mode=run.execution_mode,
        review_status=run.review_status,
        risk_score=run.risk_score,
        stubbed=bool((run.output or {}).get("stubbed")),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get("", response_model=list[StageCatalogItem], summary="The 12-stage catalog")
async def get_catalog(user: StageRunner) -> list[StageCatalogItem]:
    return [StageCatalogItem(**item) for item in service.catalog()]


@router.get(
    "/courses/{course_id}/stages",
    response_model=list[StageStatus],
    summary="Per-course stage board (catalog + latest run)",
)
async def course_stages(
    course_id: uuid.UUID, session: SessionDep, user: StageRunner
) -> list[StageStatus]:
    rows = await service.list_course_stages(session, user, course_id)
    return [
        StageStatus(
            key=r["key"],
            order=r["order"],
            title=r["title"],
            description=r["description"],
            risk=r["risk"],
            default_execution=r["default_execution"],
            promotes_to=r["promotes_to"],
            last_run=_run_summary(r["last_run"]),
        )
        for r in rows
    ]


@router.post(
    "/courses/{course_id}/stages/{stage_key}/run",
    response_model=StageRunOut,
    summary="Run or re-run a stage feature",
)
async def run_stage(
    course_id: uuid.UUID,
    stage_key: str,
    payload: RunStageRequest,
    session: SessionDep,
    user: StageRunner,
) -> StageRunOut:
    run = await service.run_stage(session, user, course_id, stage_key, payload)
    await session.commit()
    await session.refresh(run)
    return StageRunOut.model_validate(run)


@router.get(
    "/courses/{course_id}/runs",
    response_model=list[StageRunOut],
    summary="List stage runs for a course",
)
async def list_runs(
    course_id: uuid.UUID,
    session: SessionDep,
    user: StageRunner,
    stage_key: Annotated[str | None, Query()] = None,
) -> list[StageRunOut]:
    runs = await service.list_runs(session, user, course_id, stage_key)
    return [StageRunOut.model_validate(r) for r in runs]


@router.get(
    "/runs/{run_id}",
    response_model=StageRunOut,
    summary="Stage run detail (incl. council transcript)",
)
async def get_run(run_id: uuid.UUID, session: SessionDep, user: StageRunner) -> StageRunOut:
    run = await service.load_run(session, user, run_id)
    return StageRunOut.model_validate(run)


@router.post(
    "/runs/{run_id}/approve",
    response_model=StageRunOut,
    summary="SME approves a stage run",
)
async def approve_run(
    run_id: uuid.UUID,
    payload: ReviewRequest,
    session: SessionDep,
    user: StageReviewer,
) -> StageRunOut:
    run = await service.review_run(session, user, run_id, approve=True, note=payload.note)
    await session.commit()
    await session.refresh(run)
    return StageRunOut.model_validate(run)


@router.post(
    "/runs/{run_id}/reject",
    response_model=StageRunOut,
    summary="SME rejects a stage run",
)
async def reject_run(
    run_id: uuid.UUID,
    payload: ReviewRequest,
    session: SessionDep,
    user: StageReviewer,
) -> StageRunOut:
    run = await service.review_run(session, user, run_id, approve=False, note=payload.note)
    await session.commit()
    await session.refresh(run)
    return StageRunOut.model_validate(run)


__all__ = ["router"]
