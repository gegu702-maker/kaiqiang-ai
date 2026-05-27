from __future__ import annotations

import logging
from typing import Any

from postgrest.exceptions import APIError
from supabase import Client

from app.services.avatar_video import generate_avatar_video
from app.services.billing import get_generation_limits
from app.services.script_generator import generate_video_script
from app.services.tts import synthesize_speech_to_storage
from app.services.voice_clone_provider import assert_clone_owner
from app.services.video_render import render_product_video

logger = logging.getLogger(__name__)


def _missing_generation_error_column(error: APIError) -> bool:
    message = str(error)
    return "generation_error" in message and ("PGRST204" in message or "schema cache" in message)


def update_video_task(supabase: Client, task_id: str, payload: dict[str, Any]) -> None:
    try:
        supabase.table("video_tasks").update(payload).eq("id", task_id).execute()
    except APIError as error:
        if "generation_error" not in payload or not _missing_generation_error_column(error):
            raise
        compatible_payload = dict(payload)
        compatible_payload.pop("generation_error", None)
        supabase.table("video_tasks").update(compatible_payload).eq("id", task_id).execute()


def log_task(supabase: Client, *, task_id: str, level: str, message: str, data: dict[str, Any] | None = None) -> None:
    try:
        supabase.table("task_logs").insert(
            {
                "task_id": task_id,
                "level": level,
                "message": message,
                "data": data or {},
            }
        ).execute()
    except Exception:
        logger.exception("Failed to insert task log for task_id=%s", task_id)


def update_task_status(supabase: Client, task_id: str, status: str, error: str = "") -> None:
    payload: dict[str, Any] = {"status": status}
    if error:
        payload["generation_error"] = error
    elif status in {"processing", "completed"}:
        payload["generation_error"] = ""
    update_video_task(supabase, task_id, payload)
    queue_status = {"waiting": "waiting", "processing": "processing", "failed": "failed", "completed": "completed"}.get(status)
    if queue_status:
        try:
            supabase.table("task_queue").update({"status": queue_status, "error_message": error}).eq("task_id", task_id).execute()
        except Exception:
            logger.exception("Failed to update queue status for task_id=%s", task_id)


def update_queue_status(supabase: Client, task_id: str, status: str, error: str = "") -> None:
    try:
        supabase.table("task_queue").update({"status": status, "error_message": error}).eq("task_id", task_id).execute()
    except Exception:
        logger.exception("Failed to update queue status for task_id=%s", task_id)


async def process_video_task(supabase: Client, task: dict[str, Any]) -> dict[str, Any]:
    task_id = task["id"]
    user_id = task.get("user_id")
    user_email = task.get("user_email")
    if not user_id:
        raise RuntimeError("Task missing user_id")

    limits = get_generation_limits(supabase, user_id=user_id, email=user_email)
    log_task(supabase, task_id=task_id, level="info", message="Pipeline started", data=limits)

    update_task_status(supabase, task_id, "processing")
    update_queue_status(supabase, task_id, "processing")
    script_package = await generate_video_script(
        product_name=task["product_name"],
        product_highlights=task.get("product_highlights") or task.get("script") or "",
        target_audience=task.get("target_audience") or "",
        video_style=task.get("video_style") or "hard_sell",
        max_seconds=limits["max_seconds"],
        use_digital_human=bool(task.get("use_digital_human", True)),
    )
    update_video_task(
        supabase,
        task_id,
        {
            "script": script_package["script"],
            "hook": script_package["hook"],
            "selling_points": script_package["selling_points"],
            "shot_list": script_package["shot_list"],
            "title_options": script_package["title_options"],
            "caption": script_package["caption"],
            "cover_text": script_package["cover_text"],
            "cover_prompt": script_package["cover_prompt"],
            "hashtags": script_package["hashtags"],
            "comment_prompt": script_package["comment_prompt"],
            "closing_cta": script_package["closing_cta"],
            "admin_workflow": script_package["admin_workflow"],
        },
    )
    log_task(supabase, task_id=task_id, level="info", message="Script generated")

    update_queue_status(supabase, task_id, "processing")
    voice_clone = None
    if task.get("use_cloned_voice") and task.get("voice_clone_id"):
        update_queue_status(supabase, task_id, "processing")
        voice_clone = assert_clone_owner(supabase, user_id=user_id, voice_clone_id=task["voice_clone_id"])
        log_task(supabase, task_id=task_id, level="info", message="Using cloned voice", data={"voice_id": voice_clone.get("voice_id"), "provider": voice_clone.get("provider")})

    tts_result = await synthesize_speech_to_storage(
        supabase,
        text=script_package["narration_script"],
        voice_clone=voice_clone,
        folder=f"tts/{task_id}",
    )
    update_video_task(
        supabase,
        task_id,
        {
            "cloned_voice_url": tts_result["audio_url"],
            "voice_url": tts_result["audio_url"],
            "voice_duration": tts_result["duration"],
        },
    )
    log_task(supabase, task_id=task_id, level="info", message="TTS generated", data={"duration": tts_result["duration"]})

    update_queue_status(supabase, task_id, "processing")
    avatar = await generate_avatar_video(
        supabase,
        audio_url=tts_result["audio_url"],
        avatar_id=task.get("heygen_avatar_id") or task.get("avatar_id") or "",
        scene_prompt=script_package["hook"],
    )
    update_video_task(
        supabase,
        task_id,
        {
            "talking_video_url": avatar.get("talking_video_url"),
            "heygen_video_id": avatar.get("video_id") or task.get("heygen_video_id") or "",
        },
    )
    log_task(supabase, task_id=task_id, level="info", message="Avatar step completed", data=avatar)

    update_queue_status(supabase, task_id, "processing")
    final_video_url = await render_product_video(
        supabase,
        product_name=task["product_name"],
        image_url=task["image_url"],
        audio_url=tts_result["audio_url"],
        subtitle_text=script_package["subtitle_text"],
        watermark=limits["watermark"],
        max_seconds=limits["max_seconds"],
    )
    update_video_task(
        supabase,
        task_id,
        {
            "result_video_url": final_video_url,
            "status": "completed",
            "subtitle_status": "completed",
            "generation_error": "",
        },
    )
    try:
        supabase.table("task_queue").update({"status": "completed", "error_message": ""}).eq("task_id", task_id).execute()
    except Exception:
        logger.exception("Failed to mark task_queue success for task_id=%s", task_id)
    log_task(supabase, task_id=task_id, level="info", message="Pipeline success", data={"final_video_url": final_video_url})
    return {"final_video_url": final_video_url}
