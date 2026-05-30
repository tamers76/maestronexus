"""AI provider/model registry.

Single source of truth for which LLM vendors and models the platform knows
about, and which are currently enabled (based on configured credentials in
settings). Feature code (tutor, content generation, ...) should resolve
providers through this registry and never import a vendor SDK directly
(docs/06, docs/18 D12).

Add a new vendor by:
  1. adding its credential field(s) to ``Settings`` (app/core/config.py),
  2. adding a ``ProviderSpec`` entry to ``PROVIDER_REGISTRY`` below.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import Settings, settings


@dataclass(frozen=True)
class ProviderSpec:
    """Static description of an LLM vendor and the models we support for it."""

    key: str
    label: str
    models: list[str] = field(default_factory=list)
    # Name of the Settings attribute that holds the API key for this provider.
    api_key_field: str = ""

    def is_enabled(self, cfg: Settings) -> bool:
        if not self.api_key_field:
            return False
        return bool(getattr(cfg, self.api_key_field, None))


# Known vendors and the models exposed for each. Extend freely.
PROVIDER_REGISTRY: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        key="openai",
        label="OpenAI",
        models=["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3-mini"],
        api_key_field="openai_api_key",
    ),
    "anthropic": ProviderSpec(
        key="anthropic",
        label="Anthropic",
        models=["claude-3-7-sonnet", "claude-3-5-sonnet", "claude-3-5-haiku"],
        api_key_field="anthropic_api_key",
    ),
    "azure_openai": ProviderSpec(
        key="azure_openai",
        label="Azure OpenAI",
        models=["gpt-4o", "gpt-4o-mini"],
        api_key_field="azure_openai_api_key",
    ),
    "google": ProviderSpec(
        key="google",
        label="Google Gemini",
        models=["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        api_key_field="google_api_key",
    ),
}


def enabled_providers(cfg: Settings = settings) -> list[ProviderSpec]:
    """Return the providers that have credentials configured."""

    return [spec for spec in PROVIDER_REGISTRY.values() if spec.is_enabled(cfg)]


def get_provider(key: str) -> ProviderSpec | None:
    return PROVIDER_REGISTRY.get(key)


def default_provider(cfg: Settings = settings) -> ProviderSpec | None:
    """The configured default provider, if it is enabled."""

    spec = PROVIDER_REGISTRY.get(cfg.ai_default_provider)
    if spec is not None and spec.is_enabled(cfg):
        return spec
    return None
