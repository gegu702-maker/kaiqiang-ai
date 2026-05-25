from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.billing import quota_router, router as billing_router
from app.api.cosyvoice import router as cosyvoice_router
from app.api.debug import router as debug_router
from app.api.health import router as health_router
from app.api.tasks import router as tasks_router
from app.api.voice_clone import router as voice_clone_router
from app.core.config import settings
from app.services.task_worker import worker_loop
import asyncio

app = FastAPI(title="AI Digital Human API", version="0.1.0")


@app.on_event("startup")
async def start_worker() -> None:
    if settings.enable_task_worker:
        asyncio.create_task(worker_loop())

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def root_health() -> dict[str, str]:
    return {"status": "ok"}

app.include_router(health_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(quota_router, prefix="/api")
app.include_router(voice_clone_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin")
app.include_router(cosyvoice_router, prefix="/api")
app.include_router(debug_router)
