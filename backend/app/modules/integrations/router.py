"""Integrations module: connectors + the runtime AI settings control center (docs/10).

AI settings surface under ``/api/v1/integrations/ai-settings`` (all gated by
``integration.manage``). This is the admin's single place to control API keys,
the LLM Council defaults, and per-stage configuration (mode, models, prompts).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.audit import record_audit
from app.core.deps import Principal, SessionDep, require_permission
from app.modules.integrations import service
from app.modules.integrations.schemas import (
    AiSettingsResponse,
    AiSettingsUpdate,
    ModelOption,
    TestConnectionRequest,
    TestConnectionResponse,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])

SettingsManager = Annotated[Principal, Depends(require_permission("integration.manage"))]


@router.get("", summary="Integrations module status")
async def module_status() -> dict:
    return {"module": "integrations", "status": "ready"}


def _response(config: dict) -> AiSettingsResponse:
    return AiSettingsResponse(
        config=service.masked_config(config),
        catalog=service.stage_catalog(),
        resolved=service.resolved_view(config),
        recommended_prompts=service.recommended_prompts_all(),
        managed_providers=service.MANAGED_PROVIDERS,
    )


@router.get(
    "/ai-settings",
    response_model=AiSettingsResponse,
    summary="Get AI/council/stage settings (secrets masked)",
)
async def get_ai_settings(session: SessionDep, user: SettingsManager) -> AiSettingsResponse:
    row = await service.get_or_create(session, user.tenant_id)
    await session.commit()
    return _response(row.config)


@router.put(
    "/ai-settings",
    response_model=AiSettingsResponse,
    summary="Update AI/council/stage settings (partial, deep-merged)",
)
async def update_ai_settings(
    payload: AiSettingsUpdate, session: SessionDep, user: SettingsManager
) -> AiSettingsResponse:
    patch = payload.model_dump(exclude_none=True)
    row = await service.update(session, user.tenant_id, patch)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="ai.settings.update",
        object_type="ai_settings",
        object_id=row.id,
        metadata={"keys": sorted(patch.keys())},
    )
    await session.commit()
    return _response(row.config)


@router.post(
    "/ai-settings/test-connection",
    response_model=TestConnectionResponse,
    summary="Test a provider's API connection",
)
async def test_connection(
    payload: TestConnectionRequest, session: SessionDep, user: SettingsManager
) -> TestConnectionResponse:
    row = await service.get_or_create(session, user.tenant_id)
    await session.commit()
    stored_key, stored_url = service._provider_creds(row.config, payload.provider)
    # Prefer the unsaved value typed into the form; ignore masked/empty so the
    # stored secret still wins when the field was left untouched.
    typed = payload.api_key
    api_key = typed if (typed and not service._is_masked(typed)) else stored_key
    base_url = payload.base_url or stored_url
    result = await service.test_connection(payload.provider, api_key=api_key, base_url=base_url)
    return TestConnectionResponse(**result)


@router.get(
    "/ai-settings/models",
    response_model=list[ModelOption],
    summary="List selectable models for a provider",
)
async def list_models(
    session: SessionDep,
    user: SettingsManager,
    provider: Annotated[str, Query(min_length=1, max_length=64)] = "openai",
) -> list[ModelOption]:
    row = await service.get_or_create(session, user.tenant_id)
    await session.commit()
    api_key, base_url = service._provider_creds(row.config, provider)
    models = await service.list_models(provider, api_key=api_key, base_url=base_url)
    return [ModelOption(**m) for m in models]


@router.get(
    "/ai-settings/recommended-prompts",
    summary="Per-stage recommended member + chairman prompts",
)
async def recommended_prompts(user: SettingsManager) -> dict:
    return {"data": service.recommended_prompts_all()}


@router.post(
    "/ai-settings/stages/{stage_key}/reset-prompts",
    response_model=AiSettingsResponse,
    summary="Reset a stage's prompts to recommended defaults",
)
async def reset_stage_prompts(
    stage_key: str, session: SessionDep, user: SettingsManager
) -> AiSettingsResponse:
    row = await service.reset_stage_prompts(session, user.tenant_id, stage_key)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="ai.settings.reset_prompts",
        object_type="ai_settings",
        object_id=row.id,
        metadata={"stage_key": stage_key},
    )
    await session.commit()
    return _response(row.config)


__all__ = ["router"]
