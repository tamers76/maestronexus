"""AI cross-cutting models (docs/06, docs/12).

AI-generated content is never published directly: it lands in
``AIGeneratedContent`` with a ``review_status`` and only flows into a real
``ContentItem`` after human approval (docs/07).
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class AIInteraction(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "ai_interactions"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    agent: Mapped[str] = mapped_column(String(64), nullable=False, default="tutor")
    context_refs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    messages: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class AIGeneratedContent(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "ai_generated_content"

    interaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_interactions.id", ondelete="SET NULL"), nullable=True
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, default="content_item")
    draft: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")


__all__ = ["AIInteraction", "AIGeneratedContent"]
