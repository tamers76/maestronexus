"""Notifications module: multi-channel delivery (docs/09, docs/10)."""

from fastapi import APIRouter

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", summary="Notifications module status")
async def module_status() -> dict:
    return {"module": "notifications", "status": "scaffolded"}
