"""IAM models: organization, identity, RBAC, and audit log (docs/02, docs/12, docs/14).

These are the platform's foundational entities. Other modules reference them by
table name (e.g. ``ForeignKey("users.id")``) without importing the classes.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPKMixin,
)

# ── Organization ────────────────────────────────────────────────────────────


class Tenant(UUIDPKMixin, TimestampMixin, Base):
    """An institution — the multi-tenant isolation boundary."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Campus(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "campuses"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Department(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Program(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "programs"

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)


# ── Identity ──────────────────────────────────────────────────────────────


class User(UUIDPKMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nullable: SSO/OIDC users may never set a local password.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Role(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_roles_tenant_key"),)

    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)


class Permission(UUIDPKMixin, TimestampMixin, Base):
    """Global capability catalog (not tenant-scoped)."""

    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)


class RolePermission(UUIDPKMixin, Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class UserRole(UUIDPKMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )


class LearnerProfile(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "learner_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    goals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class TeacherAssignment(UUIDPKMixin, TimestampMixin, Base):
    """Links a teacher/TA user to a class (object-level scope, docs/02)."""

    __tablename__ = "teacher_assignments"
    __table_args__ = (UniqueConstraint("user_id", "class_id", name="uq_teacher_assignment"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # FK to classes.id (owned by the enrollment module) by table name.
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_in_class: Mapped[str] = mapped_column(String(32), nullable=False, default="teacher")


# ── Audit ──────────────────────────────────────────────────────────────────


class AuditLog(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Append-only trail of privileged actions (docs/14)."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_logs_object", "object_type", "object_id"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    audit_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


__all__ = [
    "Tenant",
    "Campus",
    "Department",
    "Program",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "UserRole",
    "LearnerProfile",
    "TeacherAssignment",
    "AuditLog",
]
