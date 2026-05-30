"""Projects module: project CRUD, rubrics, per-learner submissions, and the
object-scoped teacher grading queue (docs/08, docs/13).

Permissions: ``project.grade`` gates teacher management + grading; ``project.submit``
gates a learner submitting their own work. Object-level scope (own classes only)
is enforced in :mod:`app.modules.projects.service`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, SessionDep, require_permission
from app.core.schemas import Page, PageParams
from app.modules.projects import service
from app.modules.projects.schemas import (
    FeedbackOut,
    GradeIn,
    GradeOut,
    GradeResult,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    RubricIn,
    RubricOut,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionListItem,
    SubmissionOut,
)

router = APIRouter(prefix="/projects", tags=["projects"])

GradePerm = Annotated[object, Depends(require_permission("project.grade"))]
SubmitPerm = Annotated[object, Depends(require_permission("project.submit"))]
PageDep = Annotated[PageParams, Depends()]


# ── Project CRUD (teacher management via project.grade) ──────────────────────


@router.post("", response_model=ProjectOut, summary="Create a project on a node")
async def create_project(
    payload: ProjectCreate, user: CurrentUser, session: SessionDep, _: GradePerm
) -> ProjectOut:
    project = await service.create_project(session, user, payload)
    return ProjectOut.model_validate(project)


@router.get("", response_model=Page[ProjectOut], summary="List projects")
async def list_projects(
    user: CurrentUser,
    session: SessionDep,
    _: GradePerm,
    page: PageDep,
    node_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[ProjectOut]:
    items, total = await service.list_projects(
        session, user, node_id=node_id, limit=page.limit, offset=page.offset
    )
    return Page[ProjectOut](
        items=[ProjectOut.model_validate(p) for p in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


# ── Teacher grading queue (declared before /{project_id} to avoid capture) ────


@router.get(
    "/submissions",
    response_model=Page[SubmissionListItem],
    summary="Grading queue: own-class submissions",
)
async def grading_queue(
    user: CurrentUser,
    session: SessionDep,
    _: GradePerm,
    page: PageDep,
    class_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[SubmissionListItem]:
    items, total = await service.list_grading_queue(
        session, user, class_id=class_id, limit=page.limit, offset=page.offset
    )
    return Page[SubmissionListItem](
        items=items, total=total, limit=page.limit, offset=page.offset
    )


@router.get(
    "/submissions/{submission_id}",
    response_model=SubmissionDetail,
    summary="Submission detail for grading (own class)",
)
async def submission_detail(
    submission_id: uuid.UUID, user: CurrentUser, session: SessionDep, _: GradePerm
) -> SubmissionDetail:
    data = await service.get_submission_detail(session, user, submission_id)
    return SubmissionDetail(
        submission=SubmissionOut.model_validate(data["submission"]),
        project=ProjectOut.model_validate(data["project"]),
        learner_name=data["learner_name"],
        class_id=data["class_id"],
        class_name=data["class_name"],
        rubric=RubricOut.model_validate(data["rubric"]) if data["rubric"] else None,
        grade=GradeOut.model_validate(data["grade"]) if data["grade"] else None,
        feedback=FeedbackOut.model_validate(data["feedback"]) if data["feedback"] else None,
    )


@router.post(
    "/submissions/{submission_id}/grade",
    response_model=GradeResult,
    summary="Grade a submission against the rubric (own class)",
)
async def grade_submission(
    submission_id: uuid.UUID,
    payload: GradeIn,
    user: CurrentUser,
    session: SessionDep,
    _: GradePerm,
) -> GradeResult:
    grade, feedback = await service.grade_submission(session, user, submission_id, payload)
    return GradeResult(
        grade=GradeOut.model_validate(grade),
        feedback=FeedbackOut.model_validate(feedback) if feedback else None,
    )


# ── Single project ───────────────────────────────────────────────────────────


@router.get("/{project_id}", response_model=ProjectOut, summary="Get a project")
async def get_project(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep, _: GradePerm
) -> ProjectOut:
    project = await service.get_project(session, user, project_id)
    return ProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectOut, summary="Update a project")
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: CurrentUser,
    session: SessionDep,
    _: GradePerm,
) -> ProjectOut:
    project = await service.update_project(session, user, project_id, payload)
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=204, summary="Delete a project")
async def delete_project(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep, _: GradePerm
) -> None:
    await service.delete_project(session, user, project_id)


# ── Rubric ───────────────────────────────────────────────────────────────────


@router.put(
    "/{project_id}/rubric", response_model=RubricOut, summary="Create or replace the rubric"
)
async def set_rubric(
    project_id: uuid.UUID,
    payload: RubricIn,
    user: CurrentUser,
    session: SessionDep,
    _: GradePerm,
) -> RubricOut:
    rubric = await service.set_rubric(session, user, project_id, payload.criteria)
    return RubricOut.model_validate(rubric)


@router.get("/{project_id}/rubric", response_model=RubricOut | None, summary="Get the rubric")
async def get_rubric(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep, _: GradePerm
) -> RubricOut | None:
    rubric = await service.get_rubric(session, user, project_id)
    return RubricOut.model_validate(rubric) if rubric else None


# ── Submissions (learner-owned) ──────────────────────────────────────────────


@router.post(
    "/{project_id}/submissions",
    response_model=SubmissionOut,
    summary="Submit your own work (per learner)",
)
async def submit(
    project_id: uuid.UUID,
    payload: SubmissionCreate,
    user: CurrentUser,
    session: SessionDep,
    _: SubmitPerm,
) -> SubmissionOut:
    submission = await service.submit_project(session, user, project_id, payload.payload)
    return SubmissionOut.model_validate(submission)


@router.get(
    "/{project_id}/submissions/mine",
    response_model=list[SubmissionOut],
    summary="List your own submissions for a project",
)
async def my_submissions(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep, _: SubmitPerm
) -> list[SubmissionOut]:
    subs = await service.list_own_submissions(session, user, project_id)
    return [SubmissionOut.model_validate(s) for s in subs]
