"""Courses / Learning Graph module: courses, versions, nodes, dependencies (docs/04)."""

from fastapi import APIRouter

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", summary="Courses module status")
async def module_status() -> dict:
    return {"module": "courses", "status": "scaffolded"}
