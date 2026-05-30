"""IAM module: tenants, users, roles, permissions, auth (docs/02, docs/14)."""

from fastapi import APIRouter

router = APIRouter(prefix="/iam", tags=["iam"])


@router.get("", summary="IAM module status")
async def module_status() -> dict:
    return {"module": "iam", "status": "scaffolded"}
