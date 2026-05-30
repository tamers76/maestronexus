"""Attendance module: class-scoped sessions + per-learner records (docs/09, docs/13).

``attendance.manage`` gates all writes; object-level scope (own classes only) is
enforced in :mod:`app.modules.attendance.service`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, SessionDep, require_permission
from app.core.schemas import Page, PageParams
from app.modules.attendance import service
from app.modules.attendance.schemas import (
    ClassOut,
    RecordOut,
    RecordsBulkIn,
    RosterEntry,
    SessionCreate,
    SessionOut,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])

ManagePerm = Annotated[object, Depends(require_permission("attendance.manage"))]
PageDep = Annotated[PageParams, Depends()]


@router.get("/classes", response_model=list[ClassOut], summary="My classes (for selection)")
async def my_classes(
    user: CurrentUser, session: SessionDep, _: ManagePerm
) -> list[ClassOut]:
    classes = await service.list_classes(session, user)
    return [ClassOut.model_validate(c) for c in classes]


@router.post("/sessions", response_model=SessionOut, summary="Create a class attendance session")
async def create_session(
    payload: SessionCreate, user: CurrentUser, session: SessionDep, _: ManagePerm
) -> SessionOut:
    obj = await service.create_session(session, user, payload)
    return SessionOut.model_validate(obj)


@router.get("/sessions", response_model=Page[SessionOut], summary="List attendance sessions")
async def list_sessions(
    user: CurrentUser,
    session: SessionDep,
    _: ManagePerm,
    page: PageDep,
    class_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[SessionOut]:
    items, total = await service.list_sessions(
        session, user, class_id=class_id, limit=page.limit, offset=page.offset
    )
    return Page[SessionOut](
        items=[SessionOut.model_validate(s) for s in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/sessions/{session_id}", response_model=SessionOut, summary="Get a session")
async def get_session(
    session_id: uuid.UUID, user: CurrentUser, session: SessionDep, _: ManagePerm
) -> SessionOut:
    obj = await service.get_session(session, user, session_id)
    return SessionOut.model_validate(obj)


@router.get(
    "/sessions/{session_id}/roster",
    response_model=list[RosterEntry],
    summary="Class roster merged with current marks",
)
async def roster(
    session_id: uuid.UUID, user: CurrentUser, session: SessionDep, _: ManagePerm
) -> list[RosterEntry]:
    entries = await service.session_roster(session, user, session_id)
    return [RosterEntry.model_validate(e) for e in entries]


@router.get(
    "/sessions/{session_id}/records",
    response_model=list[RecordOut],
    summary="List records for a session",
)
async def list_records(
    session_id: uuid.UUID, user: CurrentUser, session: SessionDep, _: ManagePerm
) -> list[RecordOut]:
    records = await service.list_records(session, user, session_id)
    return [RecordOut.model_validate(r) for r in records]


@router.post(
    "/sessions/{session_id}/records",
    response_model=list[RecordOut],
    summary="Mark attendance for learners (present/absent/late/excused)",
)
async def mark_records(
    session_id: uuid.UUID,
    payload: RecordsBulkIn,
    user: CurrentUser,
    session: SessionDep,
    _: ManagePerm,
) -> list[RecordOut]:
    records = await service.mark_records(session, user, session_id, payload.records)
    return [RecordOut.model_validate(r) for r in records]
