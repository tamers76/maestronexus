"""Content & assessment models (docs/07, docs/12).

Content is versioned and gated by ``approval_status`` — only approved items are
served to learners or used to ground the AI tutor (docs/06). Media bytes live in
object storage; ``MediaAsset`` only holds the storage key + metadata.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    Base,
    CreatedByMixin,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPKMixin,
)


class ContentItem(UUIDPKMixin, TimestampMixin, CreatedByMixin, SoftDeleteMixin, Base):
    __tablename__ = "content_items"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    modality: Mapped[str] = mapped_column(String(48), nullable=False, default="text")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    body: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")


class MediaAsset(UUIDPKMixin, TenantMixin, TimestampMixin, CreatedByMixin, Base):
    __tablename__ = "media_assets"

    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True
    )


class Assessment(UUIDPKMixin, TimestampMixin, CreatedByMixin, Base):
    __tablename__ = "assessments"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(48), nullable=False, default="quiz")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Question(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "questions"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(48), nullable=False, default="mcq")
    prompt: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # answer_key is never serialized to learners.
    answer_key: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Attempt(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "attempts"

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enrollments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    responses: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["ContentItem", "MediaAsset", "Assessment", "Question", "Attempt"]
