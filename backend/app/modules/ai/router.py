"""AI module: provider abstraction, tutor, RAG, content generation (docs/06)."""

from fastapi import APIRouter

from app.core.config import settings
from app.modules.ai.providers import PROVIDER_REGISTRY, enabled_providers

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("", summary="AI module status")
async def module_status() -> dict:
    enabled = enabled_providers()
    return {
        "module": "ai",
        "status": "scaffolded",
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
