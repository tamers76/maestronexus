"""AI provider registry (docs/18 D12; docs/06).

All LLM access should go through this layer. Register vendors here and read
credentials from :class:`app.core.config.Settings`.
"""

from dataclasses import dataclass

from app.core.config import Settings

PROVIDER_REGISTRY: dict[str, "ProviderSpec"] = {}


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    label: str
    models: list[str]
    settings_attr: str

    def is_enabled(self, settings: Settings) -> bool:
        return bool(getattr(settings, self.settings_attr, None))


def _register(spec: ProviderSpec) -> None:
    PROVIDER_REGISTRY[spec.key] = spec


_register(
    ProviderSpec(
        key="openai",
        label="OpenAI",
        models=["gpt-4o-mini", "gpt-4o", "gpt-4.1"],
        settings_attr="openai_api_key",
    )
)
_register(
    ProviderSpec(
        key="anthropic",
        label="Anthropic",
        models=["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
        settings_attr="anthropic_api_key",
    )
)
_register(
    ProviderSpec(
        key="azure_openai",
        label="Azure OpenAI",
        models=["gpt-4o-mini"],
        settings_attr="azure_openai_api_key",
    )
)
_register(
    ProviderSpec(
        key="google",
        label="Google Gemini",
        models=["gemini-2.0-flash", "gemini-2.0-pro"],
        settings_attr="google_api_key",
    )
)


def enabled_providers(settings: Settings | None = None) -> list[ProviderSpec]:
    from app.core.config import settings as default_settings

    cfg = settings or default_settings
    return [spec for spec in PROVIDER_REGISTRY.values() if spec.is_enabled(cfg)]
