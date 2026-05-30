"""Courses / Learning Graph module endpoints (docs/04, docs/13, docs/14).

Surface under ``/api/v1/courses``:
  * Courses            — CRUD (soft delete)            [course.manage]
  * Course versions    — create/list/get/publish        [course.manage]
  * Learning nodes     — CRUD within a version          [graph.manage]
  * Node dependencies  — create/delete edges (acyclic)  [graph.manage]
  * Graph projection   — React-Flow-shaped read         [graph.manage]

All writes are tenant-scoped and audited (``record_audit``). The session is
committed here; services only ``flush``.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.audit import record_audit
from app.core.deps import Principal, SessionDep, require_permission
from app.core.schemas import Message, Page
from app.modules.courses import service
from app.modules.courses.schemas import (
    CourseClosOut,
    CourseCreate,
    CourseFromFormRequest,
    CourseFromSyllabusRequest,
    CourseOut,
    CourseUpdate,
    CourseVersionCreate,
    CourseVersionOut,
    CourseWithClosOut,
    GraphResponse,
    LearningNodeCreate,
    LearningNodeOut,
    LearningNodeUpdate,
    LearningOutcomeOut,
    NodeDependencyCreate,
    NodeDependencyOut,
    StageRunInfo,
)

router = APIRouter(prefix="/courses", tags=["courses"])

CourseManager = Annotated[Principal, Depends(require_permission("course.manage"))]
GraphManager = Annotated[Principal, Depends(require_permission("graph.manage"))]


# ── Courses ──────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=CourseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a course",
)
async def create_course(
    payload: CourseCreate, session: SessionDep, user: CourseManager
) -> CourseOut:
    course = await service.create_course(session, user, payload)
    result = CourseOut.model_validate(course)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="course.create",
        object_type="course",
        object_id=course.id,
    )
    await session.commit()
    return result


def _run_info(run) -> StageRunInfo | None:
    if run is None:
        return None
    return StageRunInfo(
        id=run.id,
        stage_key=run.stage_key,
        status=run.status,
        review_status=run.review_status,
        stubbed=bool((run.output or {}).get("stubbed")),
        created_at=run.created_at,
    )


@router.post(
    "/from-syllabus",
    response_model=CourseWithClosOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a course by parsing an uploaded syllabus (PDF/DOCX/text)",
)
async def create_course_from_syllabus(
    payload: CourseFromSyllabusRequest, session: SessionDep, user: CourseManager
) -> CourseWithClosOut:
    try:
        data = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content_base64 is not valid base64",
        ) from exc
    course, clos, run = await service.create_course_from_syllabus(
        session,
        user,
        filename=payload.filename,
        mime_type=payload.mime_type,
        data=data,
        title=payload.title,
    )
    result = CourseWithClosOut(
        course=CourseOut.model_validate(course),
        clos=[LearningOutcomeOut.model_validate(c) for c in clos],
        intake_run=_run_info(run),
    )
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="course.create.syllabus",
        object_type="course",
        object_id=course.id,
        metadata={"clo_count": len(clos), "stage_run_id": str(run.id)},
    )
    await session.commit()
    return result


@router.post(
    "/from-form",
    response_model=CourseWithClosOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a course manually with its CLOs",
)
async def create_course_from_form(
    payload: CourseFromFormRequest, session: SessionDep, user: CourseManager
) -> CourseWithClosOut:
    course, clos = await service.create_course_from_form(
        session,
        user,
        title=payload.title,
        description=payload.description,
        course_code=payload.course_code,
        credit_hours=payload.credit_hours,
        clos=payload.clos,
    )
    result = CourseWithClosOut(
        course=CourseOut.model_validate(course),
        clos=[LearningOutcomeOut.model_validate(c) for c in clos],
        intake_run=None,
    )
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="course.create.form",
        object_type="course",
        object_id=course.id,
        metadata={"clo_count": len(clos)},
    )
    await session.commit()
    return result


@router.get("", response_model=Page[CourseOut], summary="List courses")
async def list_courses(
    session: SessionDep,
    user: CourseManager,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[CourseOut]:
    courses, total = await service.list_courses(session, user, limit=limit, offset=offset)
    return Page[CourseOut](
        items=[CourseOut.model_validate(c) for c in courses],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{course_id}", response_model=CourseOut, summary="Get a course")
async def get_course(
    course_id: uuid.UUID, session: SessionDep, user: CourseManager
) -> CourseOut:
    course = await service.load_course(session, user, course_id)
    return CourseOut.model_validate(course)


@router.get(
    "/{course_id}/clos",
    response_model=CourseClosOut,
    summary="List a course's Course Learning Outcomes",
)
async def list_course_clos(
    course_id: uuid.UUID, session: SessionDep, user: CourseManager
) -> CourseClosOut:
    clos = await service.list_course_clos(session, user, course_id)
    intake_run = await service.latest_stage_run(session, course_id, "intake")
    refinement_run = await service.latest_stage_run(session, course_id, "clo_refinement")
    return CourseClosOut(
        clos=[LearningOutcomeOut.model_validate(c) for c in clos],
        intake_run=_run_info(intake_run),
        clo_refinement_run=_run_info(refinement_run),
    )


@router.patch("/{course_id}", response_model=CourseOut, summary="Update a course")
async def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    session: SessionDep,
    user: CourseManager,
) -> CourseOut:
    course = await service.update_course(session, user, course_id, payload)
    result = CourseOut.model_validate(course)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="course.update",
        object_type="course",
        object_id=course.id,
    )
    await session.commit()
    return result


@router.delete("/{course_id}", response_model=Message, summary="Soft-delete a course")
async def delete_course(
    course_id: uuid.UUID, session: SessionDep, user: CourseManager
) -> Message:
    course = await service.soft_delete_course(session, user, course_id)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="course.delete",
        object_type="course",
        object_id=course.id,
    )
    await session.commit()
    return Message(message="Course archived")


# ── Course versions ──────────────────────────────────────────────────────────


@router.post(
    "/{course_id}/versions",
    response_model=CourseVersionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new course version",
)
async def create_version(
    course_id: uuid.UUID,
    payload: CourseVersionCreate,
    session: SessionDep,
    user: CourseManager,
) -> CourseVersionOut:
    version = await service.create_version(session, user, course_id, payload)
    result = CourseVersionOut.model_validate(version)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="course.version.create",
        object_type="course_version",
        object_id=version.id,
    )
    await session.commit()
    return result


@router.get(
    "/{course_id}/versions",
    response_model=list[CourseVersionOut],
    summary="List course versions",
)
async def list_versions(
    course_id: uuid.UUID, session: SessionDep, user: CourseManager
) -> list[CourseVersionOut]:
    versions = await service.list_versions(session, user, course_id)
    return [CourseVersionOut.model_validate(v) for v in versions]


@router.get(
    "/versions/{version_id}",
    response_model=CourseVersionOut,
    summary="Get a course version",
)
async def get_version(
    version_id: uuid.UUID, session: SessionDep, user: CourseManager
) -> CourseVersionOut:
    version, _ = await service.load_version(session, user, version_id)
    return CourseVersionOut.model_validate(version)


@router.post(
    "/versions/{version_id}/publish",
    response_model=CourseVersionOut,
    summary="Publish a course version",
)
async def publish_version(
    version_id: uuid.UUID, session: SessionDep, user: CourseManager
) -> CourseVersionOut:
    version = await service.publish_version(session, user, version_id)
    result = CourseVersionOut.model_validate(version)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="course.version.publish",
        object_type="course_version",
        object_id=version.id,
    )
    await session.commit()
    return result


# ── Learning nodes ───────────────────────────────────────────────────────────


@router.post(
    "/versions/{version_id}/nodes",
    response_model=LearningNodeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a learning node",
)
async def create_node(
    version_id: uuid.UUID,
    payload: LearningNodeCreate,
    session: SessionDep,
    user: GraphManager,
) -> LearningNodeOut:
    node = await service.create_node(session, user, version_id, payload)
    result = service.node_to_out(node)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="graph.node.create",
        object_type="learning_node",
        object_id=node.id,
    )
    await session.commit()
    return result


@router.get(
    "/versions/{version_id}/nodes",
    response_model=list[LearningNodeOut],
    summary="List learning nodes in a version",
)
async def list_nodes(
    version_id: uuid.UUID, session: SessionDep, user: GraphManager
) -> list[LearningNodeOut]:
    nodes = await service.list_nodes(session, user, version_id)
    return [service.node_to_out(n) for n in nodes]


@router.get(
    "/versions/{version_id}/graph",
    response_model=GraphResponse,
    summary="Get the version graph shaped for React Flow",
)
async def get_graph(
    version_id: uuid.UUID, session: SessionDep, user: GraphManager
) -> GraphResponse:
    return await service.get_graph(session, user, version_id)


@router.get("/nodes/{node_id}", response_model=LearningNodeOut, summary="Get a learning node")
async def get_node(
    node_id: uuid.UUID, session: SessionDep, user: GraphManager
) -> LearningNodeOut:
    node, _, _ = await service.load_node(session, user, node_id)
    return service.node_to_out(node)


@router.patch(
    "/nodes/{node_id}", response_model=LearningNodeOut, summary="Update a learning node"
)
async def update_node(
    node_id: uuid.UUID,
    payload: LearningNodeUpdate,
    session: SessionDep,
    user: GraphManager,
) -> LearningNodeOut:
    node = await service.update_node(session, user, node_id, payload)
    result = service.node_to_out(node)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="graph.node.update",
        object_type="learning_node",
        object_id=node.id,
    )
    await session.commit()
    return result


@router.delete("/nodes/{node_id}", response_model=Message, summary="Delete a learning node")
async def delete_node(
    node_id: uuid.UUID, session: SessionDep, user: GraphManager
) -> Message:
    await service.delete_node(session, user, node_id)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="graph.node.delete",
        object_type="learning_node",
        object_id=node_id,
    )
    await session.commit()
    return Message(message="Node deleted")


# ── Node dependencies (edges) ────────────────────────────────────────────────


@router.post(
    "/versions/{version_id}/dependencies",
    response_model=NodeDependencyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a node dependency (edge)",
)
async def create_dependency(
    version_id: uuid.UUID,
    payload: NodeDependencyCreate,
    session: SessionDep,
    user: GraphManager,
) -> NodeDependencyOut:
    dep = await service.create_dependency(session, user, version_id, payload)
    result = NodeDependencyOut.model_validate(dep)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="graph.dependency.create",
        object_type="node_dependency",
        object_id=dep.id,
    )
    await session.commit()
    return result


@router.delete(
    "/dependencies/{dependency_id}",
    response_model=Message,
    summary="Delete a node dependency (edge)",
)
async def delete_dependency(
    dependency_id: uuid.UUID, session: SessionDep, user: GraphManager
) -> Message:
    await service.delete_dependency(session, user, dependency_id)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="graph.dependency.delete",
        object_type="node_dependency",
        object_id=dependency_id,
    )
    await session.commit()
    return Message(message="Dependency deleted")
