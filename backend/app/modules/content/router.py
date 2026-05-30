"""Content module HTTP surface (docs/07, docs/13).

Routes under ``/api/v1/content``. Authoring is gated by ``content.author``,
approval by ``content.ai_approve``, and learner-facing reads/attempts by
``node.progress``. Tenant isolation + object scope are enforced in ``service``.

The approval gate is enforced server-side: learner endpoints only ever return
``approval_status == "approved"`` content, and learner quiz/attempt responses
never include ``answer_key`` (docs/07).
"""

from __future__ import annotations

import base64
import binascii
import uuid
from typing import Annotated

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.audit import record_audit
from app.core.deps import CurrentUser, SessionDep, require_permission
from app.core.schemas import Page, PageParams
from app.modules.content import service
from app.modules.content.schemas import (
    AssessmentCreate,
    AssessmentDetailOut,
    AssessmentLearnerOut,
    AssessmentOut,
    AttemptCreate,
    AttemptOut,
    ContentItemCreate,
    ContentItemOut,
    ContentItemUpdate,
    MediaAssetOut,
    MediaDownloadOut,
    MediaUploadRequest,
    PresignUploadOut,
    PresignUploadRequest,
    QuestionCreate,
    QuestionLearnerOut,
    QuestionOut,
    QuestionUpdate,
)

router = APIRouter(prefix="/content", tags=["content"])

PageDep = Annotated[PageParams, Depends()]

# Permission dependencies (RBAC layer, docs/02).
AuthorDep = Annotated[CurrentUser, Depends(require_permission("content.author"))]
ApproverDep = Annotated[CurrentUser, Depends(require_permission("content.ai_approve"))]
LearnerDep = Annotated[CurrentUser, Depends(require_permission("node.progress"))]


@router.get("", summary="Content module status")
async def module_status() -> dict:
    return {"module": "content", "status": "ready"}


# ── Content items ────────────────────────────────────────────────────────────


@router.post(
    "/items",
    response_model=ContentItemOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a content item (draft)",
)
async def create_item(
    payload: ContentItemCreate, user: AuthorDep, session: SessionDep
) -> ContentItemOut:
    item = await service.create_content_item(
        session,
        user,
        node_id=payload.node_id,
        modality=payload.modality,
        body=payload.body,
        version=payload.version,
    )
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="content.item.create",
        object_type="content_item",
        object_id=item.id,
        metadata={"node_id": str(item.node_id), "modality": item.modality},
    )
    await session.commit()
    return ContentItemOut.model_validate(item)


@router.get("/items", response_model=Page[ContentItemOut], summary="List content items for a node")
async def list_items(
    user: AuthorDep,
    session: SessionDep,
    page: PageDep,
    node_id: Annotated[uuid.UUID, Query(description="Learning node to list content for")],
    approval_status: Annotated[str | None, Query()] = None,
) -> Page[ContentItemOut]:
    items, total = await service.list_content_items(
        session,
        user,
        node_id=node_id,
        approval_status=approval_status,
        approved_only=False,
        limit=page.limit,
        offset=page.offset,
    )
    return Page[ContentItemOut](
        items=[ContentItemOut.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/learner/items",
    response_model=Page[ContentItemOut],
    summary="List approved content for a node (learner)",
)
async def list_items_learner(
    user: LearnerDep,
    session: SessionDep,
    page: PageDep,
    node_id: Annotated[uuid.UUID, Query()],
) -> Page[ContentItemOut]:
    items, total = await service.list_content_items(
        session,
        user,
        node_id=node_id,
        approval_status=None,
        approved_only=True,
        limit=page.limit,
        offset=page.offset,
    )
    return Page[ContentItemOut](
        items=[ContentItemOut.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/items/{item_id}", response_model=ContentItemOut, summary="Get a content item")
async def get_item(item_id: uuid.UUID, user: AuthorDep, session: SessionDep) -> ContentItemOut:
    item = await service.get_content_item(session, user, item_id)
    return ContentItemOut.model_validate(item)


@router.patch("/items/{item_id}", response_model=ContentItemOut, summary="Update a content item")
async def update_item(
    item_id: uuid.UUID, payload: ContentItemUpdate, user: AuthorDep, session: SessionDep
) -> ContentItemOut:
    item = await service.update_content_item(
        session, user, item_id, modality=payload.modality, body=payload.body
    )
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="content.item.update",
        object_type="content_item",
        object_id=item.id,
        metadata={"version": item.version, "approval_status": item.approval_status},
    )
    await session.commit()
    return ContentItemOut.model_validate(item)


@router.post(
    "/items/{item_id}/approve",
    response_model=ContentItemOut,
    summary="Approve a content item (serves it to learners)",
)
async def approve_item(
    item_id: uuid.UUID, user: ApproverDep, session: SessionDep
) -> ContentItemOut:
    item = await service.set_approval(session, user, item_id, approved=True)
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="content.item.approve",
        object_type="content_item",
        object_id=item.id,
        metadata={"version": item.version},
    )
    await session.commit()
    return ContentItemOut.model_validate(item)


# ── Media assets ─────────────────────────────────────────────────────────────


@router.post(
    "/media",
    response_model=MediaAssetOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a media asset to object storage (base64 JSON body)",
)
async def upload_media(
    payload: MediaUploadRequest, user: AuthorDep, session: SessionDep
) -> MediaAssetOut:
    try:
        data = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content_base64 is not valid base64",
        ) from exc
    try:
        asset = await service.upload_media(
            session,
            user,
            filename=payload.filename,
            mime_type=payload.mime_type,
            data=data,
            content_item_id=payload.content_item_id,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Object storage unavailable",
        ) from exc
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="content.media.upload",
        object_type="media_asset",
        object_id=asset.id,
        metadata={"mime_type": asset.mime_type, "size_bytes": asset.size_bytes},
    )
    await session.commit()
    return MediaAssetOut.model_validate(asset)


@router.post(
    "/media/presign",
    response_model=PresignUploadOut,
    summary="Get a presigned PUT URL for a direct browser upload",
)
async def presign_media(
    payload: PresignUploadRequest, user: AuthorDep, session: SessionDep
) -> PresignUploadOut:
    try:
        asset, upload_url = await service.presign_upload(
            session,
            user,
            filename=payload.filename,
            mime_type=payload.mime_type,
            content_item_id=payload.content_item_id,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Object storage unavailable",
        ) from exc
    await session.commit()
    return PresignUploadOut(asset=MediaAssetOut.model_validate(asset), upload_url=upload_url)


@router.get(
    "/media/{asset_id}",
    response_model=MediaDownloadOut,
    summary="Get media metadata + a presigned download URL",
)
async def get_media(
    asset_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> MediaDownloadOut:
    asset = await service.get_media_asset(session, user, asset_id)
    try:
        download_url = service.presign_download(asset)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Object storage unavailable",
        ) from exc
    return MediaDownloadOut(asset=MediaAssetOut.model_validate(asset), download_url=download_url)


# ── Assessments & questions ──────────────────────────────────────────────────


@router.post(
    "/assessments",
    response_model=AssessmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an assessment (quiz)",
)
async def create_assessment(
    payload: AssessmentCreate, user: AuthorDep, session: SessionDep
) -> AssessmentOut:
    assessment = await service.create_assessment(
        session, user, node_id=payload.node_id, type_=payload.type, config=payload.config
    )
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="content.assessment.create",
        object_type="assessment",
        object_id=assessment.id,
        metadata={"node_id": str(assessment.node_id), "type": assessment.type},
    )
    await session.commit()
    return AssessmentOut.model_validate(assessment)


@router.get(
    "/assessments",
    response_model=Page[AssessmentOut],
    summary="List assessments for a node",
)
async def list_assessments(
    user: AuthorDep,
    session: SessionDep,
    page: PageDep,
    node_id: Annotated[uuid.UUID, Query()],
) -> Page[AssessmentOut]:
    rows, total = await service.list_assessments(
        session, user, node_id=node_id, limit=page.limit, offset=page.offset
    )
    return Page[AssessmentOut](
        items=[AssessmentOut.model_validate(a) for a in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/assessments/{assessment_id}",
    response_model=AssessmentDetailOut,
    summary="Get an assessment with questions (authoring view, includes answer keys)",
)
async def get_assessment(
    assessment_id: uuid.UUID, user: AuthorDep, session: SessionDep
) -> AssessmentDetailOut:
    assessment = await service.get_assessment_guarded(session, user, assessment_id)
    questions = await service.list_questions(session, assessment_id)
    return AssessmentDetailOut(
        **AssessmentOut.model_validate(assessment).model_dump(),
        questions=[QuestionOut.model_validate(q) for q in questions],
    )


@router.get(
    "/learner/assessments/{assessment_id}",
    response_model=AssessmentLearnerOut,
    summary="Get a quiz for a learner (answer keys stripped)",
)
async def get_assessment_learner(
    assessment_id: uuid.UUID, user: LearnerDep, session: SessionDep
) -> AssessmentLearnerOut:
    assessment = await service.get_assessment_guarded(session, user, assessment_id)
    questions = await service.list_questions(session, assessment_id)
    return AssessmentLearnerOut(
        id=assessment.id,
        node_id=assessment.node_id,
        type=assessment.type,
        config=assessment.config,
        questions=[QuestionLearnerOut.model_validate(q) for q in questions],
    )


@router.post(
    "/assessments/{assessment_id}/questions",
    response_model=QuestionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a question to an assessment",
)
async def add_question(
    assessment_id: uuid.UUID, payload: QuestionCreate, user: AuthorDep, session: SessionDep
) -> QuestionOut:
    question = await service.add_question(
        session,
        user,
        assessment_id,
        type_=payload.type,
        prompt=payload.prompt,
        answer_key=payload.answer_key,
        position=payload.position,
    )
    await session.commit()
    return QuestionOut.model_validate(question)


@router.patch(
    "/questions/{question_id}",
    response_model=QuestionOut,
    summary="Update a question",
)
async def update_question(
    question_id: uuid.UUID, payload: QuestionUpdate, user: AuthorDep, session: SessionDep
) -> QuestionOut:
    question = await service.update_question(
        session,
        user,
        question_id,
        type_=payload.type,
        prompt=payload.prompt,
        answer_key=payload.answer_key,
        position=payload.position,
    )
    await session.commit()
    return QuestionOut.model_validate(question)


@router.delete(
    "/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a question",
)
async def delete_question(
    question_id: uuid.UUID, user: AuthorDep, session: SessionDep
) -> None:
    await service.delete_question(session, user, question_id)
    await session.commit()


# ── Attempts ─────────────────────────────────────────────────────────────────


@router.post(
    "/attempts",
    response_model=AttemptOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit answers for an assessment (auto-graded)",
)
async def submit_attempt(
    payload: AttemptCreate, user: LearnerDep, session: SessionDep
) -> AttemptOut:
    attempt = await service.submit_attempt(
        session,
        user,
        enrollment_id=payload.enrollment_id,
        assessment_id=payload.assessment_id,
        responses=payload.responses,
    )
    await record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="content.attempt.submit",
        object_type="attempt",
        object_id=attempt.id,
        metadata={"assessment_id": str(attempt.assessment_id), "score": attempt.score},
    )
    await session.commit()
    return AttemptOut.model_validate(attempt)


@router.get(
    "/attempts/{attempt_id}",
    response_model=AttemptOut,
    summary="Get an attempt result",
)
async def get_attempt(
    attempt_id: uuid.UUID, user: LearnerDep, session: SessionDep
) -> AttemptOut:
    attempt = await service.get_attempt(session, user, attempt_id)
    return AttemptOut.model_validate(attempt)
