import asyncio
import logging
import os
from collections.abc import Coroutine
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.avatar import router as avatar_router
from app.api.billing import quota_router, router as billing_router
from app.api.cosyvoice import router as cosyvoice_router
from app.api.debug import router as debug_router
from app.api.health import router as health_router
from app.api.tasks import router as tasks_router
from app.api.viral import router as viral_router
from app.api.voice_clone import router as voice_clone_router
from app.core.config import settings
from app.services.autodl_client import autodl_idle_shutdown_loop
from app.services.asr_service import asr_worker_status
from app.services.task_worker import worker_loop
from app.services.viral_job_worker import viral_job_worker_loop

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Digital Human API", version="0.1.0")
background_tasks: dict[str, asyncio.Task[None]] = {}


def _track_background_task(name: str, coroutine: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coroutine, name=name)
    background_tasks[name] = task

    def report_exit(completed: asyncio.Task[None]) -> None:
        if completed.cancelled():
            logger.info("Background task stopped name=%s outcome=cancelled", name)
            return
        error = completed.exception()
        if error is None:
            logger.error("Background task stopped unexpectedly name=%s outcome=returned", name)
        else:
            logger.error(
                "Background task stopped unexpectedly name=%s outcome=failed",
                name,
                exc_info=(type(error), error, error.__traceback__),
            )

    task.add_done_callback(report_exit)


@app.on_event("startup")
async def start_worker() -> None:
    if settings.enable_task_worker:
        _track_background_task("task-worker", worker_loop())
    if settings.viral_async_jobs_enabled:
        _track_background_task("viral-job-worker", viral_job_worker_loop())
    _track_background_task("autodl-idle-shutdown", autodl_idle_shutdown_loop())

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

@app.get("/health")
def root_health() -> dict[str, object]:
    # Process liveness remains the deployment health contract. ASR readiness is
    # reported separately so a lazy model load never makes health permanently fail.
    return {"status": "ok", "asr": asr_worker_status()}


@app.get("/api/diagnostics/preview-readiness")
def preview_readiness() -> dict[str, object]:
    if settings.app_environment != "preview":
        raise HTTPException(status_code=404, detail="Not found")

    expected_tasks = {"autodl-idle-shutdown"}
    if settings.enable_task_worker:
        expected_tasks.add("task-worker")
    if settings.viral_async_jobs_enabled:
        expected_tasks.add("viral-job-worker")
    worker_states = {
        name: "running" if (task := background_tasks.get(name)) and not task.done() else "stopped"
        for name in sorted(expected_tasks)
    }
    ready = all(state == "running" for state in worker_states.values())
    return {
        "status": "ok" if ready else "degraded",
        "deployment": {
            "id": os.getenv("RAILWAY_DEPLOYMENT_ID", "local"),
            "commit_sha": os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown"),
            "service": os.getenv("RAILWAY_SERVICE_NAME", "local"),
        },
        "cors": {"allowed_origins": settings.allowed_origins},
        "async_jobs_enabled": settings.viral_async_jobs_enabled,
        "background_tasks": worker_states,
    }

app.include_router(health_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(avatar_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(quota_router, prefix="/api")
app.include_router(voice_clone_router, prefix="/api")
app.include_router(viral_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin")
app.include_router(cosyvoice_router, prefix="/api")
app.include_router(debug_router)
