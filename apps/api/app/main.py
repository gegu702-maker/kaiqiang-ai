import asyncio
import logging
import traceback

from fastapi import FastAPI
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
from app.api.voice_clone import router as voice_clone_router
from app.core.config import settings
from app.services.autodl_client import autodl_idle_shutdown_loop
from app.services.task_worker import worker_loop

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Digital Human API", version="0.1.0")


@app.on_event("startup")
async def start_worker() -> None:
    if settings.enable_task_worker:
        asyncio.create_task(worker_loop())
    asyncio.create_task(autodl_idle_shutdown_loop())

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
        content={
            "detail": {
                "message": str(exc),
                "type": exc.__class__.__name__,
                "path": request.url.path,
                "traceback": traceback.format_exc()[-6000:],
            }
        },
    )

@app.get("/health")
def root_health() -> dict[str, str]:
    return {"status": "ok"}

app.include_router(health_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(avatar_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(quota_router, prefix="/api")
app.include_router(voice_clone_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin")
app.include_router(cosyvoice_router, prefix="/api")
app.include_router(debug_router)
