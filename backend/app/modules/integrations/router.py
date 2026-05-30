"""Integrations module: connectors and standards adapters (docs/10)."""

from fastapi import APIRouter

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", summary="Integrations module status")
async def module_status() -> dict:
    return {"module": "integrations", "status": "scaffolded"}
