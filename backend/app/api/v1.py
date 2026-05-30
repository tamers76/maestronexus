"""Aggregates all module routers under the /api/v1 prefix (docs/13_api_strategy.md)."""

from fastapi import APIRouter

from app.modules.adaptive.router import router as adaptive_router
from app.modules.ai.router import router as ai_router
from app.modules.analytics.router import router as analytics_router
from app.modules.content.router import router as content_router
from app.modules.courses.router import router as courses_router
from app.modules.iam.router import router as iam_router
from app.modules.integrations.router import router as integrations_router
from app.modules.notifications.router import router as notifications_router

api_router = APIRouter()

for module_router in (
    iam_router,
    courses_router,
    adaptive_router,
    content_router,
    ai_router,
    analytics_router,
    notifications_router,
    integrations_router,
):
    api_router.include_router(module_router)
