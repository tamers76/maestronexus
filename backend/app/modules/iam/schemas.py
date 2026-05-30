"""IAM request/response schemas (docs/13)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    # Plain login identifier (username), stored in User.email.
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    # Optional disambiguation when the same username exists in multiple tenants.
    tenant_slug: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access-token lifetime in seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    display_name: str
    is_superuser: bool
    roles: list[str]
    permissions: list[str]


# ── User administration (user.manage) ───────────────────────────────────────


class UserCreate(BaseModel):
    """Create a tenant-scoped user with an optional initial role set."""

    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    status: str = Field(default="active", pattern="^(active|suspended|invited)$")
    role_keys: list[str] = Field(default_factory=list)


class UserStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|suspended|invited)$")


class RoleAssignment(BaseModel):
    role_key: str = Field(min_length=1, max_length=64)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    display_name: str
    status: str
    is_superuser: bool
    roles: list[str] = Field(default_factory=list)
    created_at: datetime


# ── Roles & permissions catalog ──────────────────────────────────────────────


class RoleOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    description: str | None = None


# ── Audit log (audit.read) ───────────────────────────────────────────────────


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None = None
    actor_email: str | None = None
    action: str
    object_type: str | None = None
    object_id: uuid.UUID | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
