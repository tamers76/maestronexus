"""Adaptive module: progress evaluation and next-node recommendations (docs/05)."""

from fastapi import APIRouter

router = APIRouter(prefix="/adaptive", tags=["adaptive"])


@router.get("", summary="Adaptive module status")
async def module_status() -> dict:
    return {"module": "adaptive", "status": "scaffolded"}
