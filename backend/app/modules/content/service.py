"""Content & assessment service layer (docs/07).

Holds all DB/business logic so the router stays thin. Two cross-cutting concerns
live here:

* **Tenant isolation.** ``ContentItem``/``Assessment``/``Question``/``Attempt``
  have no ``tenant_id`` column; ownership is derived through the learning graph
  (``learning_nodes -> course_versions -> courses.tenant_id``) or, for attempts,
  through ``enrollments.tenant_id``. These helpers resolve that and call
  ``ensure_same_tenant`` so every entry point is guarded.
* **Auto-grading.** MCQ responses are scored against ``Question.answer_key``;
  the key never leaves this layer toward a learner.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import Principal, ensure_same_tenant
from app.core.storage import get_s3_client

# Read-only references to other modules' tables (FK target tables). We query but
# never mutate these — schema changes there are out of scope (docs/11).
from app.modules.content.models import (
    Assessment,
    Attempt,
    ContentItem,
    MediaAsset,
    Question,
)
from app.modules.courses.models import Course, CourseVersion, LearningNode
from app.modules.enrollment.models import Enrollment

# Presigned URL lifetime (seconds).
_PRESIGN_EXPIRY = 3600


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


# ── Tenant resolution ────────────────────────────────────────────────────────


async def resolve_node_tenant(session: AsyncSession, node_id: uuid.UUID) -> uuid.UUID:
    """Resolve the owning tenant of a learning node via its course.

    Raises 404 when the node does not exist so callers can't probe foreign ids.
    """

    tenant_id = (
        await session.execute(
            select(Course.tenant_id)
            .join(CourseVersion, CourseVersion.course_id == Course.id)
            .join(LearningNode, LearningNode.course_version_id == CourseVersion.id)
            .where(LearningNode.id == node_id)
        )
    ).scalar_one_or_none()
    if tenant_id is None:
        raise _not_found("Learning node")
    return tenant_id


async def _guard_node(session: AsyncSession, user: Principal, node_id: uuid.UUID) -> None:
    ensure_same_tenant(user, await resolve_node_tenant(session, node_id))


async def _assessment_or_404(session: AsyncSession, assessment_id: uuid.UUID) -> Assessment:
    assessment = await session.get(Assessment, assessment_id)
    if assessment is None:
        raise _not_found("Assessment")
    return assessment


# ── Content items ────────────────────────────────────────────────────────────


async def create_content_item(
    session: AsyncSession,
    user: Principal,
    *,
    node_id: uuid.UUID,
    modality: str,
    body: dict,
    version: int,
) -> ContentItem:
    await _guard_node(session, user, node_id)
    item = ContentItem(
        node_id=node_id,
        modality=modality,
        body=body,
        version=version,
        approval_status="draft",
        created_by=user.id,
    )
    session.add(item)
    await session.flush()
    # Load server-side defaults (created_at/updated_at) so the response model can
    # serialize them without triggering a lazy (async) load in a sync context.
    await session.refresh(item)
    return item


async def list_content_items(
    session: AsyncSession,
    user: Principal,
    *,
    node_id: uuid.UUID,
    approval_status: str | None,
    approved_only: bool,
    limit: int,
    offset: int,
) -> tuple[list[ContentItem], int]:
    await _guard_node(session, user, node_id)

    filters = [ContentItem.node_id == node_id, ContentItem.deleted_at.is_(None)]
    if approved_only:
        filters.append(ContentItem.approval_status == "approved")
    elif approval_status is not None:
        filters.append(ContentItem.approval_status == approval_status)

    total = (
        await session.execute(select(func.count()).select_from(ContentItem).where(*filters))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(ContentItem)
                .where(*filters)
                .order_by(ContentItem.version.desc(), ContentItem.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


async def get_content_item(
    session: AsyncSession, user: Principal, item_id: uuid.UUID, *, approved_only: bool = False
) -> ContentItem:
    item = await session.get(ContentItem, item_id)
    if item is None or item.deleted_at is not None:
        raise _not_found("Content item")
    if approved_only and item.approval_status != "approved":
        raise _not_found("Content item")
    await _guard_node(session, user, item.node_id)
    return item


async def update_content_item(
    session: AsyncSession,
    user: Principal,
    item_id: uuid.UUID,
    *,
    modality: str | None,
    body: dict | None,
) -> ContentItem:
    item = await get_content_item(session, user, item_id)
    if modality is not None:
        item.modality = modality
    if body is not None:
        item.body = body
    # Editing an approved item invalidates approval and bumps the version
    # (docs/07: editing approved content creates a new version).
    if item.approval_status == "approved":
        item.version += 1
        item.approval_status = "draft"
    await session.flush()
    await session.refresh(item)
    return item


async def set_approval(
    session: AsyncSession, user: Principal, item_id: uuid.UUID, *, approved: bool
) -> ContentItem:
    item = await get_content_item(session, user, item_id)
    item.approval_status = "approved" if approved else "draft"
    await session.flush()
    await session.refresh(item)
    return item


# ── Media assets ─────────────────────────────────────────────────────────────


def _build_storage_key(tenant_id: uuid.UUID, asset_id: uuid.UUID, filename: str) -> str:
    safe = filename.replace("/", "_").replace("\\", "_").strip() or "file"
    return f"{tenant_id}/media/{asset_id}/{safe}"


async def upload_media(
    session: AsyncSession,
    user: Principal,
    *,
    filename: str,
    mime_type: str,
    data: bytes,
    content_item_id: uuid.UUID | None,
) -> MediaAsset:
    """Persist bytes to object storage and record the asset row.

    Tenant ownership comes from the uploader (``MediaAsset`` carries ``tenant_id``).
    If linked to a content item, that item is tenant-checked too.
    """

    if content_item_id is not None:
        # Validates existence + tenant ownership.
        await get_content_item(session, user, content_item_id)

    asset_id = uuid.uuid4()
    storage_key = _build_storage_key(user.tenant_id, asset_id, filename)

    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=storage_key,
        Body=data,
        ContentType=mime_type,
    )

    asset = MediaAsset(
        id=asset_id,
        tenant_id=user.tenant_id,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=len(data),
        content_item_id=content_item_id,
        created_by=user.id,
    )
    session.add(asset)
    await session.flush()
    await session.refresh(asset)
    return asset


async def presign_upload(
    session: AsyncSession,
    user: Principal,
    *,
    filename: str,
    mime_type: str,
    content_item_id: uuid.UUID | None,
) -> tuple[MediaAsset, str]:
    """Record an asset row and return a presigned PUT URL the client uploads to."""

    if content_item_id is not None:
        await get_content_item(session, user, content_item_id)

    asset_id = uuid.uuid4()
    storage_key = _build_storage_key(user.tenant_id, asset_id, filename)

    client = get_s3_client()
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket, "Key": storage_key, "ContentType": mime_type},
        ExpiresIn=_PRESIGN_EXPIRY,
    )

    asset = MediaAsset(
        id=asset_id,
        tenant_id=user.tenant_id,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=0,
        content_item_id=content_item_id,
        created_by=user.id,
    )
    session.add(asset)
    await session.flush()
    await session.refresh(asset)
    return asset, upload_url


async def get_media_asset(
    session: AsyncSession, user: Principal, asset_id: uuid.UUID
) -> MediaAsset:
    asset = await session.get(MediaAsset, asset_id)
    if asset is None:
        raise _not_found("Media asset")
    ensure_same_tenant(user, asset.tenant_id)
    return asset


def presign_download(asset: MediaAsset) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": asset.storage_key},
        ExpiresIn=_PRESIGN_EXPIRY,
    )


# ── Assessments & questions ──────────────────────────────────────────────────


async def create_assessment(
    session: AsyncSession,
    user: Principal,
    *,
    node_id: uuid.UUID,
    type_: str,
    config: dict,
) -> Assessment:
    await _guard_node(session, user, node_id)
    assessment = Assessment(
        node_id=node_id,
        type=type_,
        config=config,
        created_by=user.id,
    )
    session.add(assessment)
    await session.flush()
    await session.refresh(assessment)
    return assessment


async def list_assessments(
    session: AsyncSession,
    user: Principal,
    *,
    node_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[Assessment], int]:
    await _guard_node(session, user, node_id)
    filters = [Assessment.node_id == node_id]
    total = (
        await session.execute(select(func.count()).select_from(Assessment).where(*filters))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(Assessment)
                .where(*filters)
                .order_by(Assessment.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


async def get_assessment_guarded(
    session: AsyncSession, user: Principal, assessment_id: uuid.UUID
) -> Assessment:
    assessment = await _assessment_or_404(session, assessment_id)
    await _guard_node(session, user, assessment.node_id)
    return assessment


async def list_questions(
    session: AsyncSession, assessment_id: uuid.UUID
) -> list[Question]:
    rows = (
        (
            await session.execute(
                select(Question)
                .where(Question.assessment_id == assessment_id)
                .order_by(Question.position.asc(), Question.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def add_question(
    session: AsyncSession,
    user: Principal,
    assessment_id: uuid.UUID,
    *,
    type_: str,
    prompt: dict,
    answer_key: dict,
    position: int,
) -> Question:
    await get_assessment_guarded(session, user, assessment_id)
    question = Question(
        assessment_id=assessment_id,
        type=type_,
        prompt=prompt,
        answer_key=answer_key,
        position=position,
    )
    session.add(question)
    await session.flush()
    return question


async def _question_guarded(
    session: AsyncSession, user: Principal, question_id: uuid.UUID
) -> Question:
    question = await session.get(Question, question_id)
    if question is None:
        raise _not_found("Question")
    await get_assessment_guarded(session, user, question.assessment_id)
    return question


async def update_question(
    session: AsyncSession,
    user: Principal,
    question_id: uuid.UUID,
    *,
    type_: str | None,
    prompt: dict | None,
    answer_key: dict | None,
    position: int | None,
) -> Question:
    question = await _question_guarded(session, user, question_id)
    if type_ is not None:
        question.type = type_
    if prompt is not None:
        question.prompt = prompt
    if answer_key is not None:
        question.answer_key = answer_key
    if position is not None:
        question.position = position
    await session.flush()
    return question


async def delete_question(
    session: AsyncSession, user: Principal, question_id: uuid.UUID
) -> None:
    question = await _question_guarded(session, user, question_id)
    await session.delete(question)
    await session.flush()


# ── Attempts & grading ───────────────────────────────────────────────────────


def _normalize(value: object) -> object:
    """Make scalar/list answers comparable order-insensitively."""

    if isinstance(value, list):
        return frozenset(value)
    return value


def grade_responses(questions: list[Question], responses: dict) -> float | None:
    """Auto-grade MCQ-style questions against their answer keys.

    A question is *gradable* when its ``answer_key`` carries a ``correct`` value.
    Returns the fraction correct over gradable questions, or ``None`` when none
    are auto-gradable (e.g. an essay-only assessment).
    """

    gradable = [q for q in questions if q.answer_key.get("correct") is not None]
    if not gradable:
        return None

    correct = 0
    for q in gradable:
        expected = _normalize(q.answer_key.get("correct"))
        given = _normalize(responses.get(str(q.id)))
        if given is not None and given == expected:
            correct += 1
    return correct / len(gradable)


async def _enrollment_guarded(
    session: AsyncSession, user: Principal, enrollment_id: uuid.UUID
) -> Enrollment:
    enrollment = await session.get(Enrollment, enrollment_id)
    if enrollment is None or enrollment.deleted_at is not None:
        raise _not_found("Enrollment")
    ensure_same_tenant(user, enrollment.tenant_id)
    # Object-level scope: a learner may only submit against their own enrollment.
    if not user.is_superuser and enrollment.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enrollment belongs to another learner",
        )
    return enrollment


async def submit_attempt(
    session: AsyncSession,
    user: Principal,
    *,
    enrollment_id: uuid.UUID,
    assessment_id: uuid.UUID,
    responses: dict,
) -> Attempt:
    await _enrollment_guarded(session, user, enrollment_id)
    assessment = await _assessment_or_404(session, assessment_id)
    # The assessment's node must belong to the caller's tenant.
    ensure_same_tenant(user, await resolve_node_tenant(session, assessment.node_id))

    questions = await list_questions(session, assessment_id)
    score = grade_responses(questions, responses)

    attempt = Attempt(
        enrollment_id=enrollment_id,
        assessment_id=assessment_id,
        responses=responses,
        score=score,
        submitted_at=datetime.now(UTC),
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def get_attempt(
    session: AsyncSession, user: Principal, attempt_id: uuid.UUID
) -> Attempt:
    attempt = await session.get(Attempt, attempt_id)
    if attempt is None:
        raise _not_found("Attempt")
    # Re-uses enrollment guard for tenant + ownership scope.
    await _enrollment_guarded(session, user, attempt.enrollment_id)
    return attempt
