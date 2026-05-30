"""IAM module: authentication + identity endpoints (docs/02, docs/13, docs/14).

The MVP supports email+password login for local/dev plus the JWT session model
that SSO/OIDC will also issue into. Feature modules consume auth via
``app.core.deps`` (``CurrentUser``, ``require_permission``).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.audit import record_audit
from app.core.config import settings
from app.core.deps import CurrentUser, SessionDep, ensure_same_tenant, require_permission
from app.core.schemas import Page, PageParams
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.modules.iam import service
from app.modules.iam.schemas import (
    AuditLogOut,
    LoginRequest,
    MeResponse,
    PermissionOut,
    RefreshRequest,
    RoleAssignment,
    RoleOut,
    TokenResponse,
    UserCreate,
    UserOut,
    UserStatusUpdate,
)
from app.modules.iam.service import authenticate_user

router = APIRouter(prefix="/iam", tags=["iam"])

PageParamsDep = Annotated[PageParams, Depends()]


def _tokens_for(user_id: uuid.UUID, tenant_id: uuid.UUID) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id, tenant_id),
        refresh_token=create_refresh_token(user_id, tenant_id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/auth/login", response_model=TokenResponse, summary="Username + password login")
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    user = await authenticate_user(
        session, payload.username, payload.password, payload.tenant_slug
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return _tokens_for(user.id, user.tenant_id)


@router.post("/auth/refresh", response_model=TokenResponse, summary="Exchange a refresh token")
async def refresh(payload: RefreshRequest, session: SessionDep) -> TokenResponse:
    try:
        claims = decode_token(payload.refresh_token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        ) from exc

    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    user_id = uuid.UUID(claims["sub"])
    tenant_id = uuid.UUID(claims["tid"])
    return _tokens_for(user_id, tenant_id)


@router.get("/auth/me", response_model=MeResponse, summary="Current authenticated user")
async def me(user: CurrentUser) -> MeResponse:
    return MeResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        is_superuser=user.is_superuser,
        roles=sorted(user.roles),
        permissions=sorted(user.permissions),
    )


# ── User administration (user.manage, tenant-scoped) ─────────────────────────

UserManage = Annotated[CurrentUser, Depends(require_permission("user.manage"))]
AuditRead = Annotated[CurrentUser, Depends(require_permission("audit.read"))]


def _user_out(user, roles: list[str]) -> UserOut:
    return UserOut(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        is_superuser=user.is_superuser,
        roles=roles,
        created_at=user.created_at,
    )


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tenant-scoped user",
)
async def create_user(payload: UserCreate, session: SessionDep, actor: UserManage) -> UserOut:
    if await service.email_exists(session, actor.tenant_id, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already in use in this tenant"
        )
    try:
        user = await service.create_user(session, actor.tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await record_audit(
        session,
        tenant_id=actor.tenant_id,
        actor_id=actor.id,
        action="user.create",
        object_type="user",
        object_id=user.id,
        metadata={"email": user.email, "roles": payload.role_keys},
    )
    await session.commit()
    roles = (await service.roles_for_users(session, [user.id])).get(user.id, [])
    return _user_out(user, roles)


@router.get("/users", response_model=Page[UserOut], summary="List tenant users")
async def list_users(
    session: SessionDep,
    actor: UserManage,
    page: PageParamsDep,
    search: Annotated[str | None, Query(max_length=255)] = None,
) -> Page[UserOut]:
    users, total = await service.list_users(
        session, actor.tenant_id, limit=page.limit, offset=page.offset, search=search
    )
    role_map = await service.roles_for_users(session, [u.id for u in users])
    return Page(
        items=[_user_out(u, role_map.get(u.id, [])) for u in users],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/users/{user_id}", response_model=UserOut, summary="Get a user")
async def get_user(user_id: uuid.UUID, session: SessionDep, actor: UserManage) -> UserOut:
    user = await service.get_tenant_user(session, actor.tenant_id, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    ensure_same_tenant(actor, user.tenant_id)
    roles = (await service.roles_for_users(session, [user.id])).get(user.id, [])
    return _user_out(user, roles)


@router.patch("/users/{user_id}/status", response_model=UserOut, summary="Update user status")
async def update_user_status(
    user_id: uuid.UUID,
    payload: UserStatusUpdate,
    session: SessionDep,
    actor: UserManage,
) -> UserOut:
    user = await service.get_tenant_user(session, actor.tenant_id, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    ensure_same_tenant(actor, user.tenant_id)
    previous = user.status
    await service.set_user_status(session, user, payload.status)
    await record_audit(
        session,
        tenant_id=actor.tenant_id,
        actor_id=actor.id,
        action="user.status_update",
        object_type="user",
        object_id=user.id,
        metadata={"from": previous, "to": payload.status},
    )
    await session.commit()
    roles = (await service.roles_for_users(session, [user.id])).get(user.id, [])
    return _user_out(user, roles)


@router.post("/users/{user_id}/roles", response_model=UserOut, summary="Assign a role")
async def assign_role(
    user_id: uuid.UUID,
    payload: RoleAssignment,
    session: SessionDep,
    actor: UserManage,
) -> UserOut:
    user = await service.get_tenant_user(session, actor.tenant_id, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    ensure_same_tenant(actor, user.tenant_id)
    try:
        changed = await service.assign_role(session, actor.tenant_id, user, payload.role_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if changed:
        await record_audit(
            session,
            tenant_id=actor.tenant_id,
            actor_id=actor.id,
            action="user.role_assign",
            object_type="user",
            object_id=user.id,
            metadata={"role": payload.role_key},
        )
    await session.commit()
    roles = (await service.roles_for_users(session, [user.id])).get(user.id, [])
    return _user_out(user, roles)


@router.delete("/users/{user_id}/roles/{role_key}", response_model=UserOut, summary="Revoke a role")
async def unassign_role(
    user_id: uuid.UUID,
    role_key: str,
    session: SessionDep,
    actor: UserManage,
) -> UserOut:
    user = await service.get_tenant_user(session, actor.tenant_id, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    ensure_same_tenant(actor, user.tenant_id)
    try:
        changed = await service.unassign_role(session, actor.tenant_id, user, role_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if changed:
        await record_audit(
            session,
            tenant_id=actor.tenant_id,
            actor_id=actor.id,
            action="user.role_unassign",
            object_type="user",
            object_id=user.id,
            metadata={"role": role_key},
        )
    await session.commit()
    roles = (await service.roles_for_users(session, [user.id])).get(user.id, [])
    return _user_out(user, roles)


# ── Roles & permission catalog (user.manage) ─────────────────────────────────


@router.get("/roles", response_model=list[RoleOut], summary="List roles with permissions")
async def list_roles(session: SessionDep, actor: UserManage) -> list[RoleOut]:
    rows = await service.list_roles_with_permissions(session, actor.tenant_id)
    return [
        RoleOut(
            id=role.id,
            key=role.key,
            name=role.name,
            description=role.description,
            permissions=perms,
        )
        for role, perms in rows
    ]


@router.get("/permissions", response_model=list[PermissionOut], summary="Permission catalog")
async def list_permissions(session: SessionDep, actor: UserManage) -> list[PermissionOut]:
    perms = await service.list_permissions(session)
    return [PermissionOut.model_validate(p) for p in perms]


# ── Audit log (audit.read, tenant-scoped) ────────────────────────────────────


@router.get("/audit-logs", response_model=Page[AuditLogOut], summary="List audit log entries")
async def list_audit_logs(
    session: SessionDep,
    actor: AuditRead,
    page: PageParamsDep,
    action: Annotated[str | None, Query(max_length=120)] = None,
    object_type: Annotated[str | None, Query(max_length=120)] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> Page[AuditLogOut]:
    entries, total = await service.list_audit_logs(
        session,
        actor.tenant_id,
        limit=page.limit,
        offset=page.offset,
        action=action,
        object_type=object_type,
        date_from=date_from,
        date_to=date_to,
    )
    return Page(
        items=[
            AuditLogOut(
                id=entry.id,
                actor_id=entry.actor_id,
                actor_email=actor_email,
                action=entry.action,
                object_type=entry.object_type,
                object_id=entry.object_id,
                metadata=entry.audit_metadata,
                created_at=entry.created_at,
            )
            for entry, actor_email in entries
        ],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("", summary="IAM module status")
async def module_status() -> dict:
    return {"module": "iam", "status": "ready"}
