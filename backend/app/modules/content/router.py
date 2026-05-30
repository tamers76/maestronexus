"""Content module: content items, media, assessments, projects (docs/07, docs/08)."""

from fastapi import APIRouter

router = APIRouter(prefix="/content", tags=["content"])


@router.get("", summary="Content module status")
async def module_status() -> dict:
    return {"module": "content", "status": "scaffolded"}
