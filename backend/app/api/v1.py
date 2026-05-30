"""Aggregates all module routers under the /api/v1 prefix (docs/13_api_strategy.md)."""

from fastapi import APIRouter

from app.modules.adaptive.router import router as adaptive_router
from app.modules.ai.router import router as ai_router
from app.modules.analytics.router import router as analytics_router
from app.modules.attendance.router import router as attendance_router
from app.modules.blueprint.router import router as blueprint_router
from app.modules.content.router import router as content_router
from app.modules.courses.router import router as courses_router
from app.modules.enrollment.router import router as enrollment_router
from app.modules.iam.router import router as iam_router
from app.modules.integrations.router import router as integrations_router
from app.modules.notifications.router import router as notifications_router
from app.modules.projects.router import router as projects_router
from app.modules.stages.router import router as stages_router

api_router = APIRouter()

for module_router in (
    iam_router,
    courses_router,
    enrollment_router,
    adaptive_router,
    content_router,
    projects_router,
    attendance_router,
    ai_router,
    analytics_router,
    notifications_router,
    integrations_router,
    stages_router,
    blueprint_router,
):
    api_router.include_router(module_router)
