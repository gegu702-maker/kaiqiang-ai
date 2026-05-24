from __future__ import annotations

import asyncio

from postgrest.exceptions import APIError

from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.task_pipeline import log_task, process_video_task, update_task_status
from app.services.tasks import get_task


async def worker_loop() -> None:
    if not settings.enable_task_worker:
        return
    while True:
        try:
            await process_next_task()
        except Exception:
            pass
        await asyncio.sleep(settings.task_worker_poll_seconds)


async def process_next_task() -> None:
    supabase = get_supabase()
    queue = (
        supabase.table("task_queue")
        .select("*")
        .in_("status", ["waiting", "failed"])
        .lt("attempts", 3)
        .order("created_at")
        .limit(1)
        .execute()
    )
    if not queue.data:
        return
    item = queue.data[0]
    task_id = item["task_id"]
    try:
        supabase.table("task_queue").update(
            {"status": "rendering", "attempts": int(item.get("attempts") or 0) + 1}
        ).eq("id", item["id"]).execute()
        task = get_task(supabase, task_id)
        if not task:
            raise RuntimeError("Task not found")
        await process_video_task(supabase, task)
    except Exception as error:
        message = str(error)
        update_task_status(supabase, task_id, "failed", message[:1000])
        log_task(supabase, task_id=task_id, level="error", message=message[:1000])
        if isinstance(error, APIError):
            raise
