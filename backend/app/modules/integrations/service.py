"""AI settings service: the runtime control center for LLM/council/stage config.

Owns the per-tenant :class:`AiSettings` blob and the resolution logic that merges
**tenant settings → env defaults → stage definition defaults** into the concrete
configuration the stage runner + council use. Secrets are write-only over the API
(masked on read here via :func:`masked_config`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.ai.providers import get_provider
from app.modules.integrations.models import AiSettings
from app.modules.stages.definitions import STAGE_REGISTRY, ordered_stages
from app.modules.stages.prompts import recommended_prompts

# Providers whose credentials the Settings UI manages. OpenAI and OpenRouter are
# live today; the rest are slots that degrade to the offline stub until wired.
MANAGED_PROVIDERS = ["openai", "openrouter", "anthropic", "azure_openai", "google"]

# OpenRouter is OpenAI-API-compatible; this is the public base URL used when no
# explicit override is configured (per-tenant config or settings.openrouter_base_url).
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_MASK_MARK = "\u2026"  # ellipsis used to mark a masked secret


@dataclass
class ResolvedStage:
    """Concrete per-stage execution config the runner/council consume."""

    stage_key: str
    mode: str
    provider: str
    single_model: str
    council_models: list[str]
    chairman_model: str
    member_system_prompt: str
    chairman_system_prompt: str
    api_key: str | None = None
    base_url: str | None = None
    # True when the stage relies entirely on defaults (no tenant override).
    uses_defaults: bool = True

    def public(self) -> dict:
        """Secret-free view for the Settings UI's resolved preview."""

        return {
            "stage_key": self.stage_key,
            "mode": self.mode,
            "provider": self.provider,
            "single_model": self.single_model,
            "council_models": self.council_models,
            "chairman_model": self.chairman_model,
            "member_system_prompt": self.member_system_prompt,
            "chairman_system_prompt": self.chairman_system_prompt,
            "uses_defaults": self.uses_defaults,
        }


@dataclass
class StoredSettings:
    row: AiSettings | None
    config: dict = field(default_factory=dict)


# ── Loading ───────────────────────────────────────────────────────────────────


async def _load(session: AsyncSession, tenant_id: uuid.UUID) -> AiSettings | None:
    return (
        await session.execute(select(AiSettings).where(AiSettings.tenant_id == tenant_id))
    ).scalar_one_or_none()


async def get_or_create(session: AsyncSession, tenant_id: uuid.UUID) -> AiSettings:
    row = await _load(session, tenant_id)
    if row is None:
        row = AiSettings(tenant_id=tenant_id, config={})
        session.add(row)
        await session.flush()
    return row


# ── Resolution (tenant → env → stage defaults) ──────────────────────────────────


def _provider_creds(config: dict, provider: str) -> tuple[str | None, str | None]:
    providers = config.get("providers") or {}
    p = providers.get(provider) or {}
    if provider == "openai":
        api_key = p.get("api_key") or settings.openai_api_key
        base_url = p.get("base_url") or settings.openai_base_url
        return api_key, base_url
    if provider == "openrouter":
        api_key = p.get("api_key") or settings.openrouter_api_key
        base_url = (
            p.get("base_url") or settings.openrouter_base_url or OPENROUTER_BASE_URL
        )
        return api_key, base_url
    return p.get("api_key"), p.get("base_url")


def resolve_stage(
    config: dict, stage_key: str, *, mode_override: str | None = None
) -> ResolvedStage:
    spec = STAGE_REGISTRY[stage_key]
    stages_cfg = config.get("stages") or {}
    stage_cfg = stages_cfg.get(stage_key) or {}
    council_cfg = config.get("council") or {}
    recommended = recommended_prompts(stage_key)

    mode = mode_override or stage_cfg.get("mode") or spec.default_execution
    single_model = stage_cfg.get("single_model") or settings.ai_default_model
    council_models = (
        stage_cfg.get("council_models")
        or council_cfg.get("members")
        or list(settings.council_members)
    )
    chairman_model = (
        stage_cfg.get("chairman_model")
        or council_cfg.get("chairman")
        or settings.council_chairman_model
    )
    member_prompt = (
        stage_cfg.get("member_system_prompt")
        or council_cfg.get("member_system_prompt")
        or recommended.get("member_system_prompt", "")
    )
    chairman_prompt = (
        stage_cfg.get("chairman_system_prompt")
        or council_cfg.get("chairman_system_prompt")
        or recommended.get("chairman_system_prompt", "")
    )

    provider = "openai"
    api_key, base_url = _provider_creds(config, provider)

    return ResolvedStage(
        stage_key=stage_key,
        mode=mode,
        provider=provider,
        single_model=single_model,
        council_models=list(council_models),
        chairman_model=chairman_model,
        member_system_prompt=member_prompt,
        chairman_system_prompt=chairman_prompt,
        api_key=api_key,
        base_url=base_url,
        uses_defaults=not bool(stage_cfg),
    )


async def resolve_stage_execution(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    stage_key: str,
    *,
    mode_override: str | None = None,
) -> ResolvedStage:
    """Resolve the concrete execution config for a stage from the tenant store."""

    row = await _load(session, tenant_id)
    config = row.config if row else {}
    return resolve_stage(config, stage_key, mode_override=mode_override)


# ── Masking ─────────────────────────────────────────────────────────────────────


def _mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return _MASK_MARK + value[-2:]
    return f"{value[:5]}{_MASK_MARK}{value[-4:]}"


def masked_config(config: dict) -> dict:
    """Return ``config`` with provider API keys masked (never raw secrets)."""

    out = {k: v for k, v in config.items() if k != "providers"}
    providers = config.get("providers") or {}
    masked_providers: dict = {}
    for name, creds in providers.items():
        creds = creds or {}
        masked_providers[name] = {
            "api_key": _mask_secret(creds.get("api_key")),
            "base_url": creds.get("base_url") or "",
            "configured": bool(creds.get("api_key")),
        }
    out["providers"] = masked_providers
    return out


def _is_masked(value: str | None) -> bool:
    return bool(value) and _MASK_MARK in value


# ── Update (deep-merge, secret-safe) ────────────────────────────────────────────


def _merge(base: dict, patch: dict) -> dict:
    """Recursive merge: patch wins, dicts merge, ``None`` deletes a key."""

    out = dict(base)
    for key, value in patch.items():
        if value is None:
            out.pop(key, None)
        elif isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _strip_masked_secrets(base: dict, patch: dict) -> dict:
    """Drop masked api_key values from the patch so stored secrets survive."""

    providers = patch.get("providers")
    if not isinstance(providers, dict):
        return patch
    cleaned = dict(patch)
    cleaned_providers: dict = {}
    for name, creds in providers.items():
        if not isinstance(creds, dict):
            cleaned_providers[name] = creds
            continue
        creds = dict(creds)
        creds.pop("configured", None)  # read-only display flag
        if "api_key" in creds and _is_masked(creds["api_key"]):
            creds.pop("api_key")  # keep the existing stored secret
        cleaned_providers[name] = creds
    cleaned["providers"] = cleaned_providers
    return cleaned


async def update(session: AsyncSession, tenant_id: uuid.UUID, patch: dict) -> AiSettings:
    row = await get_or_create(session, tenant_id)
    safe_patch = _strip_masked_secrets(row.config, patch)
    row.config = _merge(row.config, safe_patch)
    await session.flush()
    await session.refresh(row)
    return row


async def reset_stage_prompts(
    session: AsyncSession, tenant_id: uuid.UUID, stage_key: str
) -> AiSettings:
    row = await get_or_create(session, tenant_id)
    config = dict(row.config)
    stages_cfg = dict(config.get("stages") or {})
    stage_cfg = dict(stages_cfg.get(stage_key) or {})
    stage_cfg.pop("member_system_prompt", None)
    stage_cfg.pop("chairman_system_prompt", None)
    stages_cfg[stage_key] = stage_cfg
    config["stages"] = stages_cfg
    row.config = config
    await session.flush()
    await session.refresh(row)
    return row


# ── Views ───────────────────────────────────────────────────────────────────────


def stage_catalog() -> list[dict]:
    """Static stage metadata for the Settings UI (titles, order, risk, defaults)."""

    return [
        {
            "key": s.key,
            "order": s.order,
            "title": s.title,
            "description": s.description,
            "risk": s.risk,
            "default_execution": s.default_execution,
        }
        for s in ordered_stages()
    ]


def resolved_view(config: dict) -> list[dict]:
    """Secret-free resolved per-stage config for the UI preview."""

    return [resolve_stage(config, key).public() for key in STAGE_REGISTRY]


def recommended_prompts_all() -> dict[str, dict[str, str]]:
    return {key: recommended_prompts(key) for key in STAGE_REGISTRY}


# ── Connection test + model listing ─────────────────────────────────────────────


async def test_connection(
    provider: str, *, api_key: str | None, base_url: str | None
) -> dict:
    """Validate a provider's credentials by listing its models (OpenAI live)."""

    spec = get_provider(provider)
    if spec is None:
        return {"success": False, "message": f"Unknown provider '{provider}'"}
    if not api_key:
        return {"success": False, "message": "No API key configured for this provider."}

    if provider not in ("openai", "openrouter"):
        return {
            "success": True,
            "message": f"{spec.label}: key stored. Live testing not yet wired for this provider.",
        }

    try:
        from openai import AsyncOpenAI

        base = base_url or (OPENROUTER_BASE_URL if provider == "openrouter" else None)
        client = AsyncOpenAI(api_key=api_key, base_url=base)
        models = await client.models.list()
        count = len(getattr(models, "data", []) or [])
        return {
            "success": True,
            "message": f"{spec.label} connection OK. {count} models available.",
        }
    except Exception as exc:  # network / auth / missing SDK
        return {"success": False, "message": f"Connection failed: {exc}"}


async def list_models(
    provider: str, *, api_key: str | None, base_url: str | None
) -> list[dict]:
    """List selectable models for a provider (live when keyed, else registry)."""

    spec = get_provider(provider)
    registry_models = [{"id": m, "name": m} for m in (spec.models if spec else [])]

    if provider == "openai" and api_key:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)
            resp = await client.models.list()
            live = [
                {"id": m.id, "name": m.id}
                for m in getattr(resp, "data", []) or []
                if m.id.startswith(("gpt-", "o1", "o3", "chatgpt"))
            ]
            if live:
                live.sort(key=lambda m: m["id"])
                return live
        except Exception:  # fall back to the static registry list
            pass

    if provider == "openrouter":
        # OpenRouter's /models endpoint is public; send the key as a Bearer token
        # when configured but don't require it. Returns the full provider-namespaced
        # catalog (e.g. anthropic/claude-3.5-sonnet).
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=api_key or "no-key",
                base_url=base_url or OPENROUTER_BASE_URL,
            )
            resp = await client.models.list()
            live = [
                {"id": m.id, "name": getattr(m, "name", None) or m.id}
                for m in getattr(resp, "data", []) or []
                if getattr(m, "id", None)
            ]
            if live:
                live.sort(key=lambda m: (m["name"] or m["id"]).lower())
                return live
        except Exception:  # fall back to the (empty) static registry list
            pass

    return registry_models


__all__ = [
    "MANAGED_PROVIDERS",
    "OPENROUTER_BASE_URL",
    "ResolvedStage",
    "get_or_create",
    "resolve_stage",
    "resolve_stage_execution",
    "masked_config",
    "update",
    "reset_stage_prompts",
    "stage_catalog",
    "resolved_view",
    "recommended_prompts_all",
    "test_connection",
    "list_models",
]
