"""Adaptive module: next-node recommendations + teacher overrides (docs/05).

  * ``GET  /adaptive/enrollments/{id}/next-node``          — learner (own, ``node.progress``)
                                                             or teacher (``report.view_class``)
  * ``POST /adaptive/enrollments/{id}/next-node/override`` — teacher (``node.assign``)
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.audit import record_audit
from app.core.deps import CurrentUser, SessionDep, require_permission
from app.modules.adaptive import service
from app.modules.adaptive.schemas import NextNodeResponse, OverrideRequest
from app.modules.enrollment import service as enrollment_service

router = APIRouter(prefix="/adaptive", tags=["adaptive"])


@router.get(
    "/enrollments/{enrollment_id}/next-node",
    response_model=NextNodeResponse,
    summary="Recommended next node + human-readable reason",
)
async def next_node(
    enrollment_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> NextNodeResponse:
    enrollment = await enrollment_service.get_enrollment(session, user, enrollment_id)
    is_owner = enrollment.user_id == user.id
    if not (is_owner or user.has_permission("report.view_class")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires report.view_class to view another learner's recommendation",
        )
    result = await service.compute_next_node(session, enrollment)
    # compute_next_node may persist an engine recommendation row.
    await session.commit()
    return NextNodeResponse(
        recommendation_id=result.recommendation_id,
        recommended_node_id=result.node_id,
        node_title=result.node_title,
        node_type=result.node_type,
        reason=result.reason,
        source=result.source,
        course_complete=result.course_complete,
    )


@router.post(
    "/enrollments/{enrollment_id}/next-node/override",
    response_model=NextNodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Teacher override: assign the next node (override wins)",
)
async def override_next_node(
    enrollment_id: uuid.UUID,
    payload: OverrideRequest,
    session: SessionDep,
    user: Annotated[object, Depends(require_permission("node.assign"))],
) -> NextNodeResponse:
    enrollment = await enrollment_service.get_enrollment(session, user, enrollment_id)  # type: ignore[arg-type]
    rec, node = await service.create_override(
        session, enrollment, payload.node_id, payload.reason
    )
    await record_audit(
        session, tenant_id=enrollment.tenant_id, actor_id=user.id,  # type: ignore[attr-defined]
        action="recommendation.override", object_type="recommendation", object_id=rec.id,
        metadata={"node_id": str(payload.node_id)},
    )
    await session.commit()
    return NextNodeResponse(
        recommendation_id=rec.id,
        recommended_node_id=node.id,
        node_title=node.title,
        node_type=node.type,
        reason=rec.reason,
        source="teacher_override",
        course_complete=False,
    )
