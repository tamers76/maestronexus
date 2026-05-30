"""Enrollment & progress module (docs/05, docs/12).

Endpoints:
  * Class CRUD                         — ``class.manage``
  * Enroll a learner (pin a version)   — ``class.manage``
  * List / read enrollments + progress — learner (own, ``node.progress``) or
                                         teacher (``report.view_class``)
  * Complete a node                    — learner on own enrollment (``node.progress``)
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.audit import record_audit
from app.core.deps import CurrentUser, SessionDep, require_permission
from app.core.schemas import Page, PageParams
from app.modules.courses.models import LearningNode
from app.modules.enrollment import service
from app.modules.enrollment.schemas import (
    ClassCreate,
    ClassOut,
    ClassUpdate,
    CompleteNodeRequest,
    CompleteNodeResult,
    CourseOut,
    CourseVersionOut,
    EnrollmentCreate,
    EnrollmentDetail,
    EnrollmentOut,
    NodeEdgeOut,
    NodeProgressOut,
)
from app.modules.iam.models import User

router = APIRouter(prefix="/enrollment", tags=["enrollment"])

PageDep = Annotated[PageParams, Depends()]


def _node_progress_out(rows) -> list[NodeProgressOut]:
    return [
        NodeProgressOut(
            id=prog.id,
            node_id=prog.node_id,
            node_title=node.title,
            node_type=node.type,
            state=prog.state,
            attempts=prog.attempts,
            time_spent_seconds=prog.time_spent_seconds,
            confidence=prog.confidence,
            completed_at=prog.completed_at,
        )
        for prog, node in rows
    ]


# ── Course pickers ───────────────────────────────────────────────────────────


@router.get(
    "/courses",
    response_model=list[CourseOut],
    summary="List courses + versions (for creating classes / pinning)",
)
async def list_courses(
    session: SessionDep,
    user: Annotated[object, Depends(require_permission("class.manage"))],
) -> list[CourseOut]:
    pairs = await service.list_courses_with_versions(session, user)  # type: ignore[arg-type]
    return [
        CourseOut(
            id=course.id,
            title=course.title,
            status=course.status,
            versions=[CourseVersionOut.model_validate(v) for v in versions],
        )
        for course, versions in pairs
    ]


# ── Classes ──────────────────────────────────────────────────────────────────


@router.post(
    "/classes",
    response_model=ClassOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a class",
)
async def create_class(
    payload: ClassCreate,
    session: SessionDep,
    user: Annotated[object, Depends(require_permission("class.manage"))],
) -> ClassOut:
    obj = await service.create_class(
        session, user, course_id=payload.course_id, name=payload.name,  # type: ignore[arg-type]
        teacher_id=payload.teacher_id,
    )
    await record_audit(
        session, tenant_id=obj.tenant_id, actor_id=user.id,  # type: ignore[attr-defined]
        action="class.create", object_type="class", object_id=obj.id,
    )
    await session.commit()
    return ClassOut.model_validate(obj)


@router.get("/classes", response_model=Page[ClassOut], summary="List classes")
async def list_classes(
    session: SessionDep,
    user: Annotated[object, Depends(require_permission("class.manage"))],
    page: PageDep,
    teacher_id: uuid.UUID | None = None,
) -> Page[ClassOut]:
    rows, total = await service.list_classes(
        session, user, limit=page.limit, offset=page.offset, teacher_id=teacher_id,  # type: ignore[arg-type]
    )
    return Page(
        items=[ClassOut.model_validate(r) for r in rows],
        total=total, limit=page.limit, offset=page.offset,
    )


@router.get("/classes/{class_id}", response_model=ClassOut, summary="Get a class")
async def get_class(
    class_id: uuid.UUID,
    session: SessionDep,
    user: Annotated[object, Depends(require_permission("class.manage"))],
) -> ClassOut:
    obj = await service.get_class(session, user, class_id)  # type: ignore[arg-type]
    return ClassOut.model_validate(obj)


@router.patch("/classes/{class_id}", response_model=ClassOut, summary="Update a class")
async def update_class(
    class_id: uuid.UUID,
    payload: ClassUpdate,
    session: SessionDep,
    user: Annotated[object, Depends(require_permission("class.manage"))],
) -> ClassOut:
    obj = await service.update_class(
        session, user, class_id, name=payload.name, teacher_id=payload.teacher_id,  # type: ignore[arg-type]
    )
    await record_audit(
        session, tenant_id=obj.tenant_id, actor_id=user.id,  # type: ignore[attr-defined]
        action="class.update", object_type="class", object_id=obj.id,
    )
    await session.commit()
    return ClassOut.model_validate(obj)


# ── Enrollment ───────────────────────────────────────────────────────────────


@router.post(
    "/enrollments",
    response_model=EnrollmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll a learner (pinned to a course version)",
)
async def enroll(
    payload: EnrollmentCreate,
    session: SessionDep,
    user: Annotated[object, Depends(require_permission("class.manage"))],
) -> EnrollmentOut:
    obj = await service.enroll_learner(
        session, user, class_id=payload.class_id, user_id=payload.user_id,  # type: ignore[arg-type]
        email=payload.email, course_version_id=payload.course_version_id,
    )
    await record_audit(
        session, tenant_id=obj.tenant_id, actor_id=user.id,  # type: ignore[attr-defined]
        action="enrollment.create", object_type="enrollment", object_id=obj.id,
        metadata={"class_id": str(obj.class_id), "user_id": str(obj.user_id)},
    )
    await session.commit()
    return EnrollmentOut.model_validate(obj)


@router.get("/enrollments", response_model=Page[EnrollmentOut], summary="List enrollments")
async def list_enrollments(
    session: SessionDep,
    user: CurrentUser,
    page: PageDep,
    class_id: uuid.UUID | None = None,
    user_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[EnrollmentOut]:
    # A learner may list only their own enrollments; broader views need report.view_class.
    own_only = user_id == user.id
    if not (own_only or user.has_permission("report.view_class")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires report.view_class (or filter to your own user_id)",
        )
    rows, total = await service.list_enrollments(
        session, user, class_id=class_id, user_id=user_id, limit=page.limit, offset=page.offset,
    )
    return Page(
        items=[EnrollmentOut.model_validate(r) for r in rows],
        total=total, limit=page.limit, offset=page.offset,
    )


@router.get(
    "/me/enrollments",
    response_model=list[EnrollmentOut],
    summary="The current learner's own enrollments",
)
async def my_enrollments(
    session: SessionDep,
    user: Annotated[object, Depends(require_permission("node.progress"))],
) -> list[EnrollmentOut]:
    rows, _ = await service.list_enrollments(
        session, user, class_id=None, user_id=user.id, limit=200, offset=0,  # type: ignore[attr-defined]
    )
    return [EnrollmentOut.model_validate(r) for r in rows]


async def _authorize_enrollment_view(session, user, enrollment_id: uuid.UUID):
    enrollment = await service.get_enrollment(session, user, enrollment_id)
    is_owner = enrollment.user_id == user.id
    if not (is_owner or user.has_permission("report.view_class")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires report.view_class to view another learner's progress",
        )
    return enrollment


@router.get(
    "/enrollments/{enrollment_id}",
    response_model=EnrollmentDetail,
    summary="Enrollment detail with node states + graph edges",
)
async def get_enrollment_detail(
    enrollment_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> EnrollmentDetail:
    enrollment = await _authorize_enrollment_view(session, user, enrollment_id)
    klass = await service.get_class(session, user, enrollment.class_id)
    learner = await session.get(User, enrollment.user_id)
    rows = await service.node_progress_rows(session, enrollment_id)
    edges = await service.graph_edges(session, enrollment.course_version_id)
    return EnrollmentDetail(
        enrollment=EnrollmentOut.model_validate(enrollment),
        class_name=klass.name,
        learner_name=learner.display_name if learner else "",
        nodes=_node_progress_out(rows),
        edges=[
            NodeEdgeOut(
                source_node_id=e.source_node_id,
                target_node_id=e.target_node_id,
                dependency_type=e.dependency_type,
            )
            for e in edges
        ],
    )


@router.post(
    "/enrollments/{enrollment_id}/nodes/{node_id}/complete",
    response_model=CompleteNodeResult,
    summary="Mark a node complete (learner, own enrollment)",
)
async def complete_node(
    enrollment_id: uuid.UUID,
    node_id: uuid.UUID,
    payload: CompleteNodeRequest,
    session: SessionDep,
    user: Annotated[object, Depends(require_permission("node.progress"))],
) -> CompleteNodeResult:
    enrollment = await service.get_enrollment(session, user, enrollment_id)  # type: ignore[arg-type]
    if enrollment.user_id != user.id:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only record progress on your own enrollment",
        )
    progress, unlocked, mastered = await service.complete_node(
        session, enrollment, node_id, score=payload.score,
        time_spent_seconds=payload.time_spent_seconds, confidence=payload.confidence,
    )
    node = await session.get(LearningNode, node_id)
    await record_audit(
        session, tenant_id=enrollment.tenant_id, actor_id=user.id,  # type: ignore[attr-defined]
        action="node.complete", object_type="node_progress", object_id=progress.id,
        metadata={"node_id": str(node_id), "state": progress.state},
    )
    await session.commit()
    return CompleteNodeResult(
        node=NodeProgressOut(
            id=progress.id, node_id=progress.node_id,
            node_title=node.title if node else "", node_type=node.type if node else "",
            state=progress.state, attempts=progress.attempts,
            time_spent_seconds=progress.time_spent_seconds, confidence=progress.confidence,
            completed_at=progress.completed_at,
        ),
        unlocked_node_ids=unlocked,
        mastered=mastered,
    )
