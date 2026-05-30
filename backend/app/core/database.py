"""Async SQLAlchemy engine, session factory, declarative base, and shared mixins.

Module boundaries (per docs/11_system_architecture.md): models live inside their
owning module; cross-module access goes through service interfaces, never direct
table imports. Foreign keys reference table names (strings), so modules can link
across boundaries without importing each other's model classes.

Shared column conventions (docs/12_data_model.md):
  * UUID primary keys (``UUIDPKMixin``)
  * ``created_at`` / ``updated_at`` audit timestamps (``TimestampMixin``)
  * ``tenant_id`` on every tenant-owned table (``TenantMixin``)
  * ``deleted_at`` soft deletes for recoverable records (``SoftDeleteMixin``)
  * ``created_by`` actor reference (``CreatedByMixin``)
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by all module models."""


class UUIDPKMixin:
    """UUID primary key defaulted in Python (works before the row hits the DB)."""

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Created/updated timestamps maintained by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """``tenant_id`` FK enforcing multi-tenant isolation (docs/14)."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class SoftDeleteMixin:
    """Soft delete marker for recoverable records."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CreatedByMixin:
    """Reference to the user who created the row (nullable for system actions)."""

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request."""
    async with SessionLocal() as session:
        yield session
