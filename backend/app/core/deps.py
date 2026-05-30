"""Request-scoped auth dependencies (docs/02, docs/14).

Enforcement order mirrors docs/02:
  1. Authentication        -> ``get_current_user``
  2. Tenant isolation      -> ``ensure_same_tenant`` / ``Principal.tenant_id``
  3. Role check (RBAC)     -> ``require_permission``
  4. Object-level scope    -> module services (ownership/membership)
  5. Audit                 -> ``app.core.audit.record_audit``

Feature modules should import these rather than re-implementing auth.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import decode_token
from app.modules.iam.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# auto_error=False so we can raise our own enveloped 401 (docs/13).
_bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    """The authenticated caller, resolved once per request."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    display_name: str
    is_superuser: bool
    roles: set[str] = field(default_factory=set)
    permissions: set[str] = field(default_factory=set)

    def has_permission(self, key: str) -> bool:
        return self.is_superuser or key in self.permissions

    def has_role(self, key: str) -> bool:
        return key in self.roles


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def get_current_user(
    session: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> Principal:
    if creds is None or not creds.credentials:
        raise _unauthorized()

    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError as exc:  # expired, bad signature, malformed
        raise _unauthorized("Invalid or expired token") from exc

    if payload.get("type") != "access":
        raise _unauthorized("Wrong token type")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise _unauthorized("Malformed token subject") from exc

    user = await session.get(User, user_id)
    if user is None or user.status != "active" or user.deleted_at is not None:
        raise _unauthorized("User not found or inactive")

    # Resolve roles + flattened permissions for this user.
    role_rows = (
        (
            await session.execute(
                select(Role.key)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )

    perm_rows = (
        (
            await session.execute(
                select(Permission.key)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .join(UserRole, UserRole.role_id == RolePermission.role_id)
                .where(UserRole.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )

    return Principal(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        is_superuser=user.is_superuser,
        roles=set(role_rows),
        permissions=set(perm_rows),
    )


CurrentUser = Annotated[Principal, Depends(get_current_user)]


def require_permission(*permission_keys: str):
    """Dependency factory: caller must hold *all* listed permissions (or be superuser)."""

    async def _checker(user: CurrentUser) -> Principal:
        missing = [k for k in permission_keys if not user.has_permission(k)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission(s): {', '.join(missing)}",
            )
        return user

    return _checker


def require_role(*role_keys: str):
    """Dependency factory: caller must hold at least one of the listed roles."""

    async def _checker(user: CurrentUser) -> Principal:
        if user.is_superuser or any(user.has_role(r) for r in role_keys):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires role: {', '.join(role_keys)}",
        )

    return _checker


def ensure_same_tenant(user: Principal, resource_tenant_id: uuid.UUID) -> None:
    """Tenant-isolation guard. Superusers may cross tenants (docs/02)."""

    if user.is_superuser:
        return
    if user.tenant_id != resource_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Resource belongs to another tenant"
        )
