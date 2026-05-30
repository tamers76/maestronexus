"""Analytics module: class reports & institution dashboards (docs/09).

Read-only and tenant-scoped. RBAC gates the *kind* of view (``report.view_class``
vs ``dashboard.view_institution``); object-level scope (teachers see only their
own classes) is enforced in the service layer.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import CurrentUser, SessionDep, ensure_same_tenant, require_permission
from app.modules.analytics import service
from app.modules.analytics.schemas import ClassReport, ClassSummary, InstitutionDashboard

router = APIRouter(prefix="/analytics", tags=["analytics"])

ReportViewer = Annotated[CurrentUser, Depends(require_permission("report.view_class"))]
InstitutionViewer = Annotated[
    CurrentUser, Depends(require_permission("dashboard.view_institution"))
]


@router.get(
    "/classes",
    response_model=list[ClassSummary],
    summary="List classes the caller can report on",
)
async def list_report_classes(session: SessionDep, user: ReportViewer) -> list[ClassSummary]:
    # Institution-wide viewers (admins) see every class; teachers see own classes.
    restrict = None if user.has_permission("dashboard.view_institution") else user.id
    return await service.list_classes(session, user.tenant_id, restrict_to_user=restrict)


@router.get(
    "/classes/{class_id}/report",
    response_model=ClassReport,
    summary="Class report (enrollment, progress, attendance)",
)
async def class_report(
    class_id: uuid.UUID, session: SessionDep, user: ReportViewer
) -> ClassReport:
    cls = await service.get_class(session, user.tenant_id, class_id)
    if cls is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    ensure_same_tenant(user, cls.tenant_id)

    # Object-level scope: teachers without institution-wide access see only own classes.
    if not user.has_permission("dashboard.view_institution"):
        if not await service.user_can_view_class(session, user.id, cls):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Class belongs to another teacher",
            )
    return await service.get_class_report(session, user.tenant_id, cls)


@router.get(
    "/dashboard/institution",
    response_model=InstitutionDashboard,
    summary="Institution-wide dashboard summary",
)
async def institution_dashboard(
    session: SessionDep, user: InstitutionViewer
) -> InstitutionDashboard:
    return await service.get_institution_dashboard(session, user.tenant_id)


@router.get("", summary="Analytics module status")
async def module_status() -> dict:
    return {"module": "analytics", "status": "ready"}
