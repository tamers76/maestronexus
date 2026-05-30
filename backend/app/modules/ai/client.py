"""LLM client wrapper (docs/06, docs/18 D12).

Single entry point feature code uses to talk to a language model. It resolves a
provider + model through ``providers.py`` and either:

  * calls the real vendor SDK when credentials are configured, or
  * returns a clear, deterministic **stub** response so the tutor and content
    generation work fully offline (API keys are usually UNSET in dev).

Vendor SDKs are imported lazily *inside* this module only — no other part of the
codebase may import an LLM SDK (docs/18 D12). If the SDK is missing or a live
call fails, we log and gracefully fall back to the stub so ``app.main`` always
boots and tests never touch the network.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import Settings, settings
from app.modules.ai.providers import (
    PROVIDER_REGISTRY,
    ProviderSpec,
    default_provider,
    get_provider,
)

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    """Outcome of a completion call, including how it was produced."""

    text: str
    provider: str
    model: str
    stubbed: bool


class LLMClient:
    """Resolves a provider/model and produces completions (real or stubbed)."""

    def __init__(self, cfg: Settings = settings) -> None:
        self._cfg = cfg

    def resolve(
        self, provider_key: str | None = None, model: str | None = None
    ) -> tuple[ProviderSpec | None, str]:
        """Pick the provider spec + model name for a request.

        Falls back to the configured default provider/model. The returned spec
        may be *disabled* (no key) — callers use ``spec.is_enabled`` to decide
        between a live call and the stub.
        """

        spec = get_provider(provider_key) if provider_key else default_provider(self._cfg)
        if spec is None:
            spec = PROVIDER_REGISTRY.get(self._cfg.ai_default_provider)
        return spec, (model or self._cfg.ai_default_model)

    async def complete(
        self,
        *,
        system: str,
        user: str,
        context: str = "",
        task: str = "chat",
        provider_key: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> LLMResult:
        """Return a completion. Uses the live SDK when a key is set, else a stub.

        ``api_key`` / ``base_url`` allow a caller (e.g. the council resolving a
        tenant's runtime Ai settings) to override the env-configured credentials
        for this single call. When ``api_key`` is provided the live path is
        attempted regardless of env configuration.
        """

        spec, chosen_model = self.resolve(provider_key, model)
        provider_label = spec.key if spec else self._cfg.ai_default_provider

        live_enabled = bool(api_key) or (spec is not None and spec.is_enabled(self._cfg))
        if spec is not None and live_enabled:
            try:
                text = await self._dispatch_real(
                    spec, chosen_model, system, user, context, api_key, base_url
                )
                if text:
                    return LLMResult(text, provider=spec.key, model=chosen_model, stubbed=False)
                logger.warning("LLM %s returned empty content; using stub", spec.key)
            except Exception as exc:  # missing SDK, network, auth, quota, ...
                logger.warning(
                    "Live LLM call failed for %s; falling back to stub: %s", spec.key, exc
                )

        text = _stub_response(
            task=task, provider=provider_label, model=chosen_model, user=user, context=context
        )
        return LLMResult(text, provider=provider_label, model=chosen_model, stubbed=True)

    async def _dispatch_real(
        self,
        spec: ProviderSpec,
        model: str,
        system: str,
        user: str,
        context: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> str:
        if spec.key == "openai":
            return await self._openai_chat(model, system, user, context, api_key, base_url)
        # Other vendors are registered but not yet wired for live calls; the
        # caller transparently falls back to the deterministic stub.
        raise NotImplementedError(f"No live client implemented for provider '{spec.key}'")

    async def _openai_chat(
        self,
        model: str,
        system: str,
        user: str,
        context: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> str:
        # Lazy import: only reached when an OpenAI key is configured. Keeping it
        # here means a missing `openai` package never breaks import or tests.
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=api_key or self._cfg.openai_api_key,
            base_url=base_url or self._cfg.openai_base_url or None,
        )
        system_content = system if not context else f"{system}\n\nGrounding context:\n{context}"
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip()


# ── Deterministic offline stubs ──────────────────────────────────────────────


def _first_lines(text: str, count: int) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(f"- {ln}" for ln in lines[:count])


def _stub_response(*, task: str, provider: str, model: str, user: str, context: str) -> str:
    tag = f"[stub · {provider}/{model}]"
    question = user.strip()

    if task == "tutor":
        if context:
            return (
                f"{tag} Based on the approved course material, here is what's relevant to "
                f'"{question}":\n\n{_first_lines(context, 6)}\n\n'
                "Review the points above, then try applying them to your task. "
                "If you'd like a worked example or you're still stuck, you can escalate to your "
                "teacher."
            )
        return (
            f"{tag} I couldn't find approved course content that covers "
            f'"{question}", so I can\'t answer confidently without guessing. '
            "I'd recommend escalating this question to your teacher."
        )

    if task == "draft":
        return (
            f"{tag}\n\n"
            "## Overview\n"
            f"This is an offline-generated draft responding to the brief:\n> {question}\n\n"
            "## Key concepts\n"
            "- Core idea and why it matters\n"
            "- A concrete example learners can relate to\n"
            "- Common misconceptions to watch for\n\n"
            "## Practice\n"
            "1. A short check-for-understanding question.\n"
            "2. A small applied exercise.\n\n"
            "## Summary\n"
            "Recap the key concepts in two or three sentences.\n\n"
            "_Configure an LLM API key to replace this stub with a live generation._"
        )

    return f"{tag} {question}"


# Module-level singleton reused across requests.
llm_client = LLMClient()

__all__ = ["LLMClient", "LLMResult", "llm_client"]
