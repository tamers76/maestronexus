"""Analytics module: attendance, reports, dashboards (docs/09)."""

from fastapi import APIRouter

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", summary="Analytics module status")
async def module_status() -> dict:
    return {"module": "analytics", "status": "scaffolded"}
