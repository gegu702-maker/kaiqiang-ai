from __future__ import annotations

import asyncio
import logging

from postgrest.exceptions import APIError

from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.billing import refund_generation_usage
from app.services.task_pipeline import log_task, process_video_task, update_task_status
from app.services.tasks import get_task

logger = logging.getLogger(__name__)


async def worker_loop() -> None:
    if not settings.enable_task_worker:
        return
    while True:
        try:
            await process_next_task()
        except Exception:
            logger.exception("Task worker loop failed")
        await asyncio.sleep(settings.task_worker_poll_seconds)


async def process_next_task() -> None:
    supabase = get_supabase()
    queue = (
        supabase.table("task_queue")
        .select("*")
        .eq("status", "waiting")
        .lt("attempts", 3)
        .order("created_at")
        .limit(1)
        .execute()
    )
    if not queue.data:
        return
    item = queue.data[0]
    task_id = item["task_id"]
    next_attempt = int(item.get("attempts") or 0) + 1
    try:
        claimed = supabase.table("task_queue").update(
            {"status": "processing", "attempts": next_attempt, "error_message": ""}
        ).eq("id", item["id"]).eq("status", "waiting").execute()
        if not claimed.data:
            logger.info("Task queue item already claimed, skipping queue_id=%s task_id=%s", item.get("id"), task_id)
            return
        update_task_status(supabase, task_id, "processing")
        task = get_task(supabase, task_id)
        if not task:
            raise RuntimeError("Task not found")
        await process_video_task(supabase, task)
    except Exception as error:
        logger.exception("Task processing failed for task_id=%s", task_id)
        message = str(error)
        log_task(
            supabase,
            task_id=task_id,
            level="error",
            message=message[:1000],
            data={"attempt": next_attempt, "max_attempts": 3},
        )
        task = get_task(supabase, task_id)
        update_task_status(supabase, task_id, "failed", message[:1000])
        if task and task.get("user_id"):
            refund_generation_usage(supabase, user_id=task["user_id"], task_id=task_id)
            log_task(supabase, task_id=task_id, level="info", message="Generation credit refunded after failure")
        if isinstance(error, APIError):
            raise
