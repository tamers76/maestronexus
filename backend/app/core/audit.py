"""Audit logging helper (docs/14).

Every privileged action should call ``record_audit`` so the append-only trail in
``audit_logs`` captures who did what, to which object, in which tenant. The caller
is responsible for committing the surrounding transaction.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iam.models import AuditLog


async def record_audit(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: str,
    object_type: str | None = None,
    object_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        audit_metadata=metadata or {},
    )
    session.add(entry)
    await session.flush()
    return entry
