"""Integration connector + AI settings models (docs/10, docs/12).

Per-tenant provider config. ``AiSettings`` is the runtime, UI-editable control
center for AI/LLM behavior: API keys, the LLM Council defaults, and per-stage
configuration (mode, models, prompts). It is the source of truth that the stage
runner + council resolve against (falling back to env + stage defaults).
"""

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class IntegrationConnector(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "integration_connectors"

    category: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="inactive")


class AiSettings(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Single per-tenant blob holding all runtime AI/council/stage settings.

    Shape of ``config`` (all keys optional; resolution fills the rest):
      {
        "providers": {"openai": {"api_key": "...", "base_url": "..."}, ...},
        "council":   {"members": [...], "chairman": "...",
                      "member_system_prompt": "...", "chairman_system_prompt": "..."},
        "stages":    {"<stage_key>": {"mode": "single|council", "single_model": "...",
                      "council_models": [...], "chairman_model": "...",
                      "member_system_prompt": "...", "chairman_system_prompt": "..."}}
      }
    """

    __tablename__ = "ai_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_ai_settings_tenant"),)

    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


__all__ = ["IntegrationConnector", "AiSettings"]
