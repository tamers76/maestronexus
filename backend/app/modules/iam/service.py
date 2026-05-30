"""IAM service functions: authentication and identity lookups (docs/02, docs/14).

Keeps DB/business logic out of the router. Other modules that need identity data
should call functions here rather than importing IAM tables directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.modules.iam.models import (
    AuditLog,
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserRole,
)
from app.modules.iam.schemas import UserCreate


async def authenticate_user(
    session: AsyncSession, email: str, password: str, tenant_slug: str | None = None
) -> User | None:
    """Return the matching active user when credentials are valid, else ``None``."""

    stmt = select(User).where(
        User.email == email,
        User.status == "active",
        User.deleted_at.is_(None),
    )
    if tenant_slug:
        stmt = stmt.join(Tenant, Tenant.id == User.tenant_id).where(Tenant.slug == tenant_slug)

    users = (await session.execute(stmt)).scalars().all()
    # Ambiguous (same email across tenants) without a tenant hint -> reject.
    if len(users) != 1:
        return None

    user = users[0]
    if not verify_password(password, user.password_hash):
        return None
    return user


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


# ── User administration (tenant-scoped) ──────────────────────────────────────


async def roles_for_users(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    """Return a ``user_id -> sorted role keys`` map for the given users."""

    if not user_ids:
        return {}
    rows = (
        await session.execute(
            select(UserRole.user_id, Role.key)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids))
        )
    ).all()
    out: dict[uuid.UUID, list[str]] = {uid: [] for uid in user_ids}
    for user_id, key in rows:
        out.setdefault(user_id, []).append(key)
    return {uid: sorted(keys) for uid, keys in out.items()}


async def list_users(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    search: str | None = None,
) -> tuple[list[User], int]:
    base: Select = select(User).where(User.tenant_id == tenant_id, User.deleted_at.is_(None))
    if search:
        like = f"%{search.strip()}%"
        base = base.where(User.email.ilike(like) | User.display_name.ilike(like))

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                base.order_by(User.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), int(total)


async def get_tenant_user(
    session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> User | None:
    return (
        await session.execute(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def email_exists(session: AsyncSession, tenant_id: uuid.UUID, email: str) -> bool:
    found = (
        await session.execute(
            select(User.id).where(User.tenant_id == tenant_id, User.email == email)
        )
    ).scalar_one_or_none()
    return found is not None


async def create_user(
    session: AsyncSession, tenant_id: uuid.UUID, payload: UserCreate
) -> User:
    """Create a user and assign any requested (tenant-scoped) roles. Caller commits."""

    user = User(
        tenant_id=tenant_id,
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        status=payload.status,
    )
    session.add(user)
    await session.flush()

    if payload.role_keys:
        roles = await _resolve_roles(session, tenant_id, payload.role_keys)
        for role in roles:
            session.add(UserRole(user_id=user.id, role_id=role.id))
        await session.flush()
    return user


async def _resolve_roles(
    session: AsyncSession, tenant_id: uuid.UUID, role_keys: list[str]
) -> list[Role]:
    rows = (
        (
            await session.execute(
                select(Role).where(Role.tenant_id == tenant_id, Role.key.in_(role_keys))
            )
        )
        .scalars()
        .all()
    )
    found = {r.key for r in rows}
    missing = [k for k in role_keys if k not in found]
    if missing:
        raise ValueError(f"Unknown role(s) for tenant: {', '.join(sorted(set(missing)))}")
    return list(rows)


async def set_user_status(session: AsyncSession, user: User, status: str) -> User:
    user.status = status
    await session.flush()
    return user


async def assign_role(
    session: AsyncSession, tenant_id: uuid.UUID, user: User, role_key: str
) -> bool:
    """Grant a role to a user. Returns True if newly added, False if already held."""

    (role,) = await _resolve_roles(session, tenant_id, [role_key])
    existing = (
        await session.execute(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.flush()
    return True


async def unassign_role(
    session: AsyncSession, tenant_id: uuid.UUID, user: User, role_key: str
) -> bool:
    """Revoke a role from a user. Returns True if removed, False if not held."""

    (role,) = await _resolve_roles(session, tenant_id, [role_key])
    existing = (
        await session.execute(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
        )
    ).scalar_one_or_none()
    if existing is None:
        return False
    await session.delete(existing)
    await session.flush()
    return True


# ── Roles & permission catalog ────────────────────────────────────────────────


async def list_roles_with_permissions(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[tuple[Role, list[str]]]:
    roles = (
        (
            await session.execute(
                select(Role).where(Role.tenant_id == tenant_id).order_by(Role.name)
            )
        )
        .scalars()
        .all()
    )
    if not roles:
        return []
    role_ids = [r.id for r in roles]
    perm_rows = (
        await session.execute(
            select(RolePermission.role_id, Permission.key)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(RolePermission.role_id.in_(role_ids))
        )
    ).all()
    perms: dict[uuid.UUID, list[str]] = {r.id: [] for r in roles}
    for role_id, key in perm_rows:
        perms.setdefault(role_id, []).append(key)
    return [(r, sorted(perms.get(r.id, []))) for r in roles]


async def list_permissions(session: AsyncSession) -> list[Permission]:
    return list(
        (await session.execute(select(Permission).order_by(Permission.key))).scalars().all()
    )


# ── Audit log (tenant-scoped read) ───────────────────────────────────────────


async def list_audit_logs(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    action: str | None = None,
    object_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[tuple[AuditLog, str | None]], int]:
    base: Select = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    if action:
        base = base.where(AuditLog.action == action)
    if object_type:
        base = base.where(AuditLog.object_type == object_type)
    if date_from:
        base = base.where(AuditLog.created_at >= date_from)
    if date_to:
        base = base.where(AuditLog.created_at <= date_to)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows = (
        await session.execute(
            base.add_columns(User.email)
            .outerjoin(User, User.id == AuditLog.actor_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    entries = [(row[0], row[1]) for row in rows]
    return entries, int(total)
