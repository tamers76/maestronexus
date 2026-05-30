"""Liveness and readiness endpoints.

`/health` is a cheap liveness probe. `/health/ready` actively checks the three
backing services (Postgres, Redis, MinIO/S3) configured for local dev.
"""

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.core.redis import redis_client
from app.core.storage import get_s3_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "env": settings.app_env}


async def _check_postgres() -> tuple[bool, str]:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:  # noqa: BLE001 - report any failure to the probe
        return False, str(exc)


async def _check_redis() -> tuple[bool, str]:
    try:
        await redis_client.ping()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


async def _check_storage() -> tuple[bool, str]:
    def _head() -> None:
        get_s3_client().head_bucket(Bucket=settings.s3_bucket)

    try:
        await asyncio.to_thread(_head)
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    pg_ok, pg_msg = await _check_postgres()
    redis_ok, redis_msg = await _check_redis()
    s3_ok, s3_msg = await _check_storage()

    checks = {
        "postgres": {"ok": pg_ok, "detail": pg_msg},
        "redis": {"ok": redis_ok, "detail": redis_msg},
        "storage": {"ok": s3_ok, "detail": s3_msg},
    }
    all_ok = pg_ok and redis_ok and s3_ok
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
    )
