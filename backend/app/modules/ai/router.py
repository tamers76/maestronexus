"""AI module: provider abstraction, tutor, RAG, content generation (docs/06).

Endpoints (under ``/api/v1/ai``):
  * ``POST /ai/tutor``                      — grounded, guard-railed tutor (``tutor.use``)
  * ``POST /ai/content/draft``              — generate a draft into review (``content.ai_generate``)
  * ``GET  /ai/content/draft``              — list drafts for the tenant (``content.ai_generate``)
  * ``POST /ai/content/draft/{id}/approve`` — approve a draft (``content.ai_approve``)
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.deps import Principal, SessionDep, require_permission
from app.core.schemas import Page
from app.modules.ai import service
from app.modules.ai.providers import PROVIDER_REGISTRY, enabled_providers
from app.modules.ai.schemas import (
    DraftCreate,
    DraftRead,
    TutorRequest,
    TutorResponse,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("", summary="AI module status")
async def module_status() -> dict:
    enabled = enabled_providers()
    return {
        "module": "ai",
        "status": "ready",
        "default_provider": settings.ai_default_provider,
        "default_model": settings.ai_default_model,
        "enabled_providers": [spec.key for spec in enabled],
    }


@router.get("/providers", summary="List known AI providers and models")
async def list_providers() -> dict:
    return {
        "default_provider": settings.ai_default_provider,
        "default_model": settings.ai_default_model,
        "providers": [
            {
                "key": spec.key,
                "label": spec.label,
                "models": spec.models,
                "enabled": spec.is_enabled(settings),
            }
            for spec in PROVIDER_REGISTRY.values()
        ],
    }


# ── Tutor ─────────────────────────────────────────────────────────────────────


@router.post("/tutor", response_model=TutorResponse, summary="Ask the grounded AI tutor")
async def tutor(
    payload: TutorRequest,
    session: SessionDep,
    user: Annotated[Principal, Depends(require_permission("tutor.use"))],
) -> TutorResponse:
    outcome = await service.run_tutor(session, user, payload)
    return TutorResponse(
        interaction_id=outcome.interaction_id,
        answer=outcome.answer,
        grounded=outcome.grounded,
        refused=outcome.refused,
        escalate=outcome.escalate,
        escalation_path=outcome.escalation_path,
        sources=outcome.sources,
        provider=outcome.provider,
        model=outcome.model,
        stubbed=outcome.stubbed,
    )


# ── Content drafts ────────────────────────────────────────────────────────────


@router.post(
    "/content/draft",
    response_model=DraftRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an AI content draft (lands in review)",
)
async def create_draft(
    payload: DraftCreate,
    session: SessionDep,
    user: Annotated[Principal, Depends(require_permission("content.ai_generate"))],
) -> DraftRead:
    draft = await service.generate_draft(session, user, payload)
    return DraftRead.model_validate(draft)


@router.get(
    "/content/draft",
    response_model=Page[DraftRead],
    summary="List AI content drafts for the tenant",
)
async def list_drafts(
    session: SessionDep,
    user: Annotated[Principal, Depends(require_permission("content.ai_generate"))],
    review_status: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[DraftRead]:
    rows, total = await service.list_drafts(
        session, user, review_status=review_status, limit=limit, offset=offset
    )
    return Page[DraftRead](
        items=[DraftRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/content/draft/{draft_id}/approve",
    response_model=DraftRead,
    summary="Approve an AI content draft",
)
async def approve_draft(
    draft_id: uuid.UUID,
    session: SessionDep,
    user: Annotated[Principal, Depends(require_permission("content.ai_approve"))],
) -> DraftRead:
    draft = await service.approve_draft(session, user, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return DraftRead.model_validate(draft)
