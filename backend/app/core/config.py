"""Application settings, loaded from environment / .env via pydantic-settings."""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "The-Code Adaptive LMS"
    app_env: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # NoDecode: take the raw env string and split it ourselves (avoid JSON parsing).
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    database_url: str = (
        "postgresql+asyncpg://maestro:maestro-dev-secret123@localhost:5432/maestronexus"
    )
    redis_url: str = "redis://localhost:6379/0"

    # ── Auth / JWT ──────────────────────────────────────────────────────
    # SSO/OIDC is the production path (docs/14); local dev also supports
    # email+password login. JWT signs short-lived access tokens and longer
    # refresh tokens. Override jwt_secret in every non-local environment.
    jwt_secret: str = "dev-only-insecure-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "maestro"
    s3_secret_key: str = "maestro-dev-secret123"
    s3_bucket: str = "maestronexus"
    s3_region: str = "us-east-1"

    # ── AI / LLM providers ──────────────────────────────────────────────
    # All LLM access goes through the provider-abstraction layer (docs/18 D12;
    # docs/06). Credentials live here so config stays the single source of
    # truth; add a new vendor by adding its key field below and registering it
    # in app/modules/ai/providers.py.
    ai_default_provider: str = "openai"
    ai_default_model: str = "gpt-4o-mini"

    # ── LLM Council defaults (docs: Stages-as-Features + Council) ────────
    # Multiple models deliberate and a chairman synthesizes the final answer.
    # These env values seed a tenant's first AiSettings row and act as the
    # fallback when a stage/tenant has no explicit override. Per-stage and
    # per-tenant overrides are edited at runtime via /integrations/ai-settings.
    council_enabled: bool = True
    council_members: Annotated[list[str], NoDecode] = [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4.1-mini",
    ]
    council_chairman_model: str = "gpt-4o"
    # Stage keys whose default execution mode is "council" (all others default
    # to "single"). Comma-separated in the environment.
    council_default_stages: Annotated[list[str], NoDecode] = ["content_production"]

    # OpenAI (active)
    openai_api_key: str | None = None
    openai_base_url: str | None = None  # optional override (proxy / gateway)

    # OpenRouter (active) — OpenAI-compatible gateway to a live, provider-namespaced
    # catalog (e.g. anthropic/claude-3.5-sonnet). base_url defaults to
    # https://openrouter.ai/api/v1 when unset (resolved in the integrations service).
    openrouter_api_key: str | None = None
    openrouter_base_url: str | None = None

    # Additional vendors (set the key in .env to enable):
    anthropic_api_key: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str | None = None
    google_api_key: str | None = None

    @field_validator(
        "cors_origins",
        "council_members",
        "council_default_stages",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
