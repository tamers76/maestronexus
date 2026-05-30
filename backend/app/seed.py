"""Idempotent dev seed: tenant, permission catalog, roles, and demo users.

Run from the backend dir:

    uv run python -m app.seed

Creates (if missing):
  * tenant ``the-code`` (slug)
  * every permission in ``app.modules.iam.permissions.PERMISSIONS``
  * every role in ``ROLES`` with its default permission grants
  * demo users (login = username, password ``pass``):
      - super       (super_admin / is_superuser)
      - admin       (institution_admin)
      - designer    (course_designer)
      - teacher     (teacher)
      - learner     (learner)

Safe to run repeatedly. Also removes the older ``*@the-code.dev`` demo users.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import delete, select

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.modules.iam.models import (
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserRole,
)
from app.modules.iam.permissions import PERMISSIONS, ROLE_PERMISSIONS, ROLES

DEMO_PASSWORD = "pass"
TENANT_SLUG = "the-code"

# (username, display name, role key, is_superuser)
DEMO_USERS = [
    ("super", "Super Admin", "super_admin", True),
    ("admin", "Institution Admin", "institution_admin", False),
    ("designer", "Course Designer", "course_designer", False),
    ("teacher", "Teacher One", "teacher", False),
    ("learner", "Learner One", "learner", False),
]

# Older demo identities to remove so login stays simple.
LEGACY_DEMO_EMAILS = [
    "super@the-code.dev",
    "admin@the-code.dev",
    "designer@the-code.dev",
    "teacher@the-code.dev",
    "learner@the-code.dev",
]


async def seed() -> None:
    async with SessionLocal() as session:
        # ── Tenant ──────────────────────────────────────────────────────
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        ).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name="The-Code Demo Institution", slug=TENANT_SLUG)
            session.add(tenant)
            await session.flush()
            print(f"+ tenant {TENANT_SLUG}")

        # ── Permissions ─────────────────────────────────────────────────
        existing_perms = {
            p.key: p for p in (await session.execute(select(Permission))).scalars().all()
        }
        for key, desc in PERMISSIONS.items():
            if key not in existing_perms:
                perm = Permission(key=key, description=desc)
                session.add(perm)
                existing_perms[key] = perm
                print(f"+ permission {key}")
        await session.flush()

        # ── Roles + grants ──────────────────────────────────────────────
        existing_roles = {
            r.key: r
            for r in (await session.execute(select(Role).where(Role.tenant_id == tenant.id)))
            .scalars()
            .all()
        }
        for key, label in ROLES.items():
            role = existing_roles.get(key)
            if role is None:
                role = Role(tenant_id=tenant.id, key=key, name=label)
                session.add(role)
                await session.flush()
                existing_roles[key] = role
                print(f"+ role {key}")

            # Sync this role's permission grants.
            granted = {
                rp.permission_id
                for rp in (
                    await session.execute(
                        select(RolePermission).where(RolePermission.role_id == role.id)
                    )
                )
                .scalars()
                .all()
            }
            for perm_key in ROLE_PERMISSIONS.get(key, []):
                perm = existing_perms[perm_key]
                if perm.id not in granted:
                    session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        await session.flush()

        # ── Remove legacy email-based demo users ─────────────────────────
        legacy_ids = (
            (
                await session.execute(
                    select(User.id).where(
                        User.tenant_id == tenant.id, User.email.in_(LEGACY_DEMO_EMAILS)
                    )
                )
            )
            .scalars()
            .all()
        )
        if legacy_ids:
            await session.execute(delete(UserRole).where(UserRole.user_id.in_(legacy_ids)))
            await session.execute(delete(User).where(User.id.in_(legacy_ids)))
            await session.flush()
            print(f"- removed {len(legacy_ids)} legacy demo user(s)")

        # ── Demo users ──────────────────────────────────────────────────
        for email, name, role_key, is_super in DEMO_USERS:
            user = (
                await session.execute(
                    select(User).where(User.tenant_id == tenant.id, User.email == email)
                )
            ).scalar_one_or_none()
            if user is None:
                user = User(
                    tenant_id=tenant.id,
                    email=email,
                    display_name=name,
                    password_hash=hash_password(DEMO_PASSWORD),
                    is_superuser=is_super,
                )
                session.add(user)
                await session.flush()
                print(f"+ user {email}")
            else:
                # Keep the demo password in sync with DEMO_PASSWORD.
                user.password_hash = hash_password(DEMO_PASSWORD)

            role = existing_roles[role_key]
            has_role = (
                await session.execute(
                    select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
                )
            ).scalar_one_or_none()
            if has_role is None:
                session.add(UserRole(user_id=user.id, role_id=role.id))

        await session.commit()
        print("seed complete.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
