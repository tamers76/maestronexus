"""Projects service: tenant + object-scope logic kept out of the router (docs/08).

Object-level scope is the heart of this module: a teacher may only see and grade
submissions from *their own* classes. Ownership is resolved through
``TeacherAssignment`` / ``Class.teacher_id`` and the learner's ``Enrollment``
pinned to the project node's course version.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.deps import Principal
from app.modules.courses.models import Course, CourseVersion, LearningNode
from app.modules.enrollment.models import Class, Enrollment
from app.modules.iam.models import TeacherAssignment, User
from app.modules.projects.models import Feedback, Grade, Project, ProjectSubmission, Rubric
from app.modules.projects.schemas import (
    GradeIn,
    ProjectCreate,
    ProjectUpdate,
    SubmissionListItem,
)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


async def _teacher_class_ids(session: AsyncSession, user: Principal) -> set[uuid.UUID]:
    """Class ids the teacher owns or is assigned to, within their tenant."""

    owned = (
        await session.execute(
            select(Class.id).where(Class.tenant_id == user.tenant_id, Class.teacher_id == user.id)
        )
    ).scalars().all()
    assigned = (
        await session.execute(
            select(TeacherAssignment.class_id)
            .join(Class, Class.id == TeacherAssignment.class_id)
            .where(Class.tenant_id == user.tenant_id, TeacherAssignment.user_id == user.id)
        )
    ).scalars().all()
    return set(owned) | set(assigned)


async def _node_tenant_id(session: AsyncSession, node_id: uuid.UUID) -> uuid.UUID | None:
    """Resolve the owning tenant of a learning node via its course (docs/04)."""

    return (
        await session.execute(
            select(Course.tenant_id)
            .join(CourseVersion, CourseVersion.course_id == Course.id)
            .join(LearningNode, LearningNode.course_version_id == CourseVersion.id)
            .where(LearningNode.id == node_id)
        )
    ).scalar_one_or_none()


# ── Project CRUD ─────────────────────────────────────────────────────────────


async def create_project(session: AsyncSession, user: Principal, data: ProjectCreate) -> Project:
    tenant_id = await _node_tenant_id(session, data.node_id)
    if tenant_id is None:
        raise _not_found("Learning node not found")
    if not user.is_superuser and tenant_id != user.tenant_id:
        raise _forbidden("Node belongs to another tenant")

    project = Project(
        node_id=data.node_id,
        title=data.title,
        instructions=data.instructions,
        collaborative=data.collaborative,
        max_submissions=data.max_submissions,
        created_by=user.id,
    )
    session.add(project)
    await session.flush()
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="project.create",
        object_type="project",
        object_id=project.id,
        metadata={"node_id": str(data.node_id)},
    )
    await session.commit()
    await session.refresh(project)
    return project


async def _get_project_in_tenant(
    session: AsyncSession, user: Principal, project_id: uuid.UUID
) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise _not_found("Project not found")
    if not user.is_superuser:
        tenant_id = await _node_tenant_id(session, project.node_id)
        if tenant_id != user.tenant_id:
            raise _forbidden("Project belongs to another tenant")
    return project


async def get_project(
    session: AsyncSession, user: Principal, project_id: uuid.UUID
) -> Project:
    return await _get_project_in_tenant(session, user, project_id)


async def list_projects(
    session: AsyncSession,
    user: Principal,
    *,
    node_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Project], int]:
    base = (
        select(Project)
        .join(LearningNode, LearningNode.id == Project.node_id)
        .join(CourseVersion, CourseVersion.id == LearningNode.course_version_id)
        .join(Course, Course.id == CourseVersion.course_id)
    )
    if not user.is_superuser:
        base = base.where(Course.tenant_id == user.tenant_id)
    if node_id is not None:
        base = base.where(Project.node_id == node_id)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    items = (
        (
            await session.execute(
                base.order_by(Project.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(items), total


async def update_project(
    session: AsyncSession, user: Principal, project_id: uuid.UUID, data: ProjectUpdate
) -> Project:
    project = await _get_project_in_tenant(session, user, project_id)
    fields = data.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(project, key, value)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="project.update",
        object_type="project",
        object_id=project.id,
        metadata={"fields": sorted(fields.keys())},
    )
    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(
    session: AsyncSession, user: Principal, project_id: uuid.UUID
) -> None:
    project = await _get_project_in_tenant(session, user, project_id)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="project.delete",
        object_type="project",
        object_id=project.id,
    )
    await session.delete(project)
    await session.commit()


# ── Rubric ───────────────────────────────────────────────────────────────────


async def set_rubric(
    session: AsyncSession, user: Principal, project_id: uuid.UUID, criteria: dict
) -> Rubric:
    """Create or replace the project's rubric (one rubric per project for the MVP)."""

    await _get_project_in_tenant(session, user, project_id)
    rubric = (
        await session.execute(select(Rubric).where(Rubric.project_id == project_id))
    ).scalar_one_or_none()
    if rubric is None:
        rubric = Rubric(project_id=project_id, criteria=criteria)
        session.add(rubric)
    else:
        rubric.criteria = criteria
    await session.commit()
    await session.refresh(rubric)
    return rubric


async def get_rubric(
    session: AsyncSession, user: Principal, project_id: uuid.UUID
) -> Rubric | None:
    await _get_project_in_tenant(session, user, project_id)
    return (
        await session.execute(select(Rubric).where(Rubric.project_id == project_id))
    ).scalar_one_or_none()


# ── Learner submissions ─────────────────────────────────────────────────────


async def _learner_enrollment_for_node(
    session: AsyncSession, learner_id: uuid.UUID, node_id: uuid.UUID
) -> Enrollment | None:
    """The learner's active enrollment whose course version owns the project node."""

    return (
        await session.execute(
            select(Enrollment)
            .join(LearningNode, LearningNode.course_version_id == Enrollment.course_version_id)
            .where(
                Enrollment.user_id == learner_id,
                Enrollment.deleted_at.is_(None),
                LearningNode.id == node_id,
            )
        )
    ).scalars().first()


async def submit_project(
    session: AsyncSession, user: Principal, project_id: uuid.UUID, payload: dict
) -> ProjectSubmission:
    """A learner submits their *own* per-learner submission (docs/08)."""

    project = await _get_project_in_tenant(session, user, project_id)
    enrollment = await _learner_enrollment_for_node(session, user.id, project.node_id)
    if enrollment is None:
        raise _forbidden("You are not enrolled in a class for this project")

    prior = (
        await session.execute(
            select(func.count())
            .select_from(ProjectSubmission)
            .where(
                ProjectSubmission.project_id == project_id,
                ProjectSubmission.learner_id == user.id,
            )
        )
    ).scalar_one()
    if project.max_submissions > 0 and prior >= project.max_submissions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Submission limit reached for this project",
        )

    submission = ProjectSubmission(
        project_id=project_id,
        learner_id=user.id,
        attempt_no=prior + 1,
        status="submitted",
        payload=payload,
    )
    session.add(submission)
    await session.flush()
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="project.submit",
        object_type="project_submission",
        object_id=submission.id,
        metadata={"project_id": str(project_id), "attempt_no": submission.attempt_no},
    )
    await session.commit()
    await session.refresh(submission)
    return submission


async def list_own_submissions(
    session: AsyncSession, user: Principal, project_id: uuid.UUID
) -> list[ProjectSubmission]:
    await _get_project_in_tenant(session, user, project_id)
    return list(
        (
            await session.execute(
                select(ProjectSubmission)
                .where(
                    ProjectSubmission.project_id == project_id,
                    ProjectSubmission.learner_id == user.id,
                )
                .order_by(ProjectSubmission.attempt_no.desc())
            )
        )
        .scalars()
        .all()
    )


# ── Teacher grading queue (object-scoped) ─────────────────────────────────────


def _scoped_submission_query(user: Principal, class_ids: set[uuid.UUID]):
    """Submissions joined to the owning class through the learner's enrollment."""

    query = (
        select(ProjectSubmission, Project, User.display_name, Class.id, Class.name)
        .join(Project, Project.id == ProjectSubmission.project_id)
        .join(LearningNode, LearningNode.id == Project.node_id)
        .join(
            Enrollment,
            and_(
                Enrollment.user_id == ProjectSubmission.learner_id,
                Enrollment.course_version_id == LearningNode.course_version_id,
                Enrollment.deleted_at.is_(None),
            ),
        )
        .join(Class, Class.id == Enrollment.class_id)
        .join(User, User.id == ProjectSubmission.learner_id)
        .where(Class.tenant_id == user.tenant_id)
    )
    if not user.is_superuser:
        query = query.where(Enrollment.class_id.in_(class_ids))
    return query


async def list_grading_queue(
    session: AsyncSession,
    user: Principal,
    *,
    class_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[SubmissionListItem], int]:
    class_ids = await _teacher_class_ids(session, user)
    if not class_ids and not user.is_superuser:
        return [], 0

    query = _scoped_submission_query(user, class_ids)
    if class_id is not None:
        query = query.where(Enrollment.class_id == class_id)

    total = (
        await session.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()

    rows = (
        await session.execute(
            query.order_by(ProjectSubmission.created_at.desc()).limit(limit).offset(offset)
        )
    ).all()

    sub_ids = [row[0].id for row in rows]
    grades = await _grades_by_submission(session, sub_ids)

    items = [
        SubmissionListItem(
            id=sub.id,
            project_id=sub.project_id,
            project_title=project.title,
            learner_id=sub.learner_id,
            learner_name=learner_name,
            class_id=class_id_,
            class_name=class_name,
            attempt_no=sub.attempt_no,
            status=sub.status,
            graded=sub.id in grades,
            score=grades.get(sub.id),
            created_at=sub.created_at,
        )
        for sub, project, learner_name, class_id_, class_name in rows
    ]
    return items, total


async def _grades_by_submission(
    session: AsyncSession, submission_ids: list[uuid.UUID]
) -> dict[uuid.UUID, float | None]:
    if not submission_ids:
        return {}
    rows = (
        await session.execute(
            select(Grade.submission_id, Grade.score).where(
                Grade.submission_id.in_(submission_ids)
            )
        )
    ).all()
    return {sub_id: score for sub_id, score in rows}


async def _submission_scope(
    session: AsyncSession, user: Principal, submission_id: uuid.UUID
):
    """Return ``(submission, project, learner_name, class_id, class_name)`` if the
    caller may act on this submission, else raise 404/403."""

    submission = await session.get(ProjectSubmission, submission_id)
    if submission is None:
        raise _not_found("Submission not found")

    class_ids = await _teacher_class_ids(session, user)
    query = _scoped_submission_query(user, class_ids).where(
        ProjectSubmission.id == submission_id
    )
    row = (await session.execute(query)).first()
    if row is None:
        raise _forbidden("Submission is not in one of your classes")
    return row


async def get_submission_detail(
    session: AsyncSession, user: Principal, submission_id: uuid.UUID
):
    submission, project, learner_name, class_id, class_name = await _submission_scope(
        session, user, submission_id
    )
    rubric = (
        await session.execute(select(Rubric).where(Rubric.project_id == project.id))
    ).scalar_one_or_none()
    grade = (
        await session.execute(select(Grade).where(Grade.submission_id == submission_id))
    ).scalar_one_or_none()
    feedback = None
    if grade is not None:
        feedback = (
            await session.execute(select(Feedback).where(Feedback.grade_id == grade.id))
        ).scalars().first()
    return {
        "submission": submission,
        "project": project,
        "learner_name": learner_name,
        "class_id": class_id,
        "class_name": class_name,
        "rubric": rubric,
        "grade": grade,
        "feedback": feedback,
    }


async def grade_submission(
    session: AsyncSession, user: Principal, submission_id: uuid.UUID, data: GradeIn
) -> tuple[Grade, Feedback | None]:
    """Upsert the grade + teacher feedback for an own-class submission (docs/08)."""

    submission, _project, _name, _class_id, _class_name = await _submission_scope(
        session, user, submission_id
    )

    grade = (
        await session.execute(select(Grade).where(Grade.submission_id == submission_id))
    ).scalar_one_or_none()
    if grade is None:
        grade = Grade(
            submission_id=submission_id,
            grader_id=user.id,
            score=data.score,
            rubric_scores=data.rubric_scores,
        )
        session.add(grade)
    else:
        grade.grader_id = user.id
        grade.score = data.score
        grade.rubric_scores = data.rubric_scores
    await session.flush()

    feedback: Feedback | None = None
    if data.feedback:
        feedback = (
            await session.execute(
                select(Feedback).where(
                    Feedback.grade_id == grade.id, Feedback.author_type == "teacher"
                )
            )
        ).scalars().first()
        if feedback is None:
            feedback = Feedback(grade_id=grade.id, author_type="teacher", body=data.feedback)
            session.add(feedback)
        else:
            feedback.body = data.feedback
        await session.flush()

    submission.status = "graded"
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="project.grade",
        object_type="project_submission",
        object_id=submission_id,
        metadata={"score": data.score},
    )
    await session.commit()
    await session.refresh(grade)
    if feedback is not None:
        await session.refresh(feedback)
    return grade, feedback
