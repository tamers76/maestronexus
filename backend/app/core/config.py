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

    # OpenAI (active)
    openai_api_key: str | None = None
    openai_base_url: str | None = None  # optional override (proxy / gateway)

    # Additional vendors (set the key in .env to enable):
    anthropic_api_key: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str | None = None
    google_api_key: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
