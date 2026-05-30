"""Adaptive engine model: recommendations (docs/05, docs/12).

The rule-based MVP engine writes a ``Recommendation`` (with a human-readable
reason) per enrollment. ``source`` distinguishes engine output from a teacher
override, which always wins (docs/15 acceptance criteria).
"""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPKMixin


class Recommendation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enrollments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recommended_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # "engine" | "teacher_override"
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="engine")


__all__ = ["Recommendation"]
