"""FastAPI application entrypoint for the maestronexus modular monolith."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.errors import register_exception_handlers
from app.core.redis import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing to warm yet; connections are created lazily.
    yield
    # Shutdown: release pooled resources cleanly.
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="The-Code Adaptive LMS (maestronexus) — API-first modular monolith.",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# Liveness / readiness at the root.
app.include_router(health_router)
# Versioned API surface.
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "api": settings.api_v1_prefix,
    }
