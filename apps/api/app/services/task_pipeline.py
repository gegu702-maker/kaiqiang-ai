from __future__ import annotations

from typing import Any

from supabase import Client

from app.services.avatar_video import generate_avatar_video
from app.services.billing import get_generation_limits
from app.services.script_generator import generate_video_script
from app.services.tts import synthesize_speech_to_storage
from app.services.voice_clone_provider import assert_clone_owner
from app.services.video_render import render_product_video


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
        pass


def update_task_status(supabase: Client, task_id: str, status: str, error: str = "") -> None:
    payload: dict[str, Any] = {"status": status}
    if error:
        payload["generation_error"] = error
    supabase.table("video_tasks").update(payload).eq("id", task_id).execute()
    try:
        supabase.table("task_queue").update({"status": status, "error_message": error}).eq("task_id", task_id).execute()
    except Exception:
        pass


async def process_video_task(supabase: Client, task: dict[str, Any]) -> dict[str, Any]:
    task_id = task["id"]
    user_id = task.get("user_id")
    user_email = task.get("user_email")
    if not user_id:
        raise RuntimeError("Task missing user_id")

    limits = get_generation_limits(supabase, user_id=user_id, email=user_email)
    log_task(supabase, task_id=task_id, level="info", message="Pipeline started", data=limits)

    update_task_status(supabase, task_id, "generating_script")
    script_package = await generate_video_script(
        product_name=task["product_name"],
        product_highlights=task.get("product_highlights") or task.get("script") or "",
        target_audience=task.get("target_audience") or "",
        video_style=task.get("video_style") or "hard_sell",
        max_seconds=limits["max_seconds"],
        use_digital_human=bool(task.get("use_digital_human", True)),
    )
    supabase.table("video_tasks").update(
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
        }
    ).eq("id", task_id).execute()
    log_task(supabase, task_id=task_id, level="info", message="Script generated")

    update_task_status(supabase, task_id, "generating_voice")
    voice_clone = None
    if task.get("use_cloned_voice") and task.get("voice_clone_id"):
        update_task_status(supabase, task_id, "cloning_voice")
        voice_clone = assert_clone_owner(supabase, user_id=user_id, voice_clone_id=task["voice_clone_id"])
        log_task(supabase, task_id=task_id, level="info", message="Using cloned voice", data={"voice_id": voice_clone.get("voice_id"), "provider": voice_clone.get("provider")})

    tts_result = await synthesize_speech_to_storage(
        supabase,
        text=script_package["narration_script"],
        voice_clone=voice_clone,
        folder=f"tts/{task_id}",
    )
    supabase.table("video_tasks").update(
        {
            "cloned_voice_url": tts_result["audio_url"],
            "voice_duration": tts_result["duration"],
        }
    ).eq("id", task_id).execute()
    log_task(supabase, task_id=task_id, level="info", message="TTS generated", data={"duration": tts_result["duration"]})

    update_task_status(supabase, task_id, "generating_avatar")
    avatar = await generate_avatar_video(
        supabase,
        audio_url=tts_result["audio_url"],
        avatar_id=task.get("heygen_avatar_id") or task.get("avatar_id") or "",
        scene_prompt=script_package["hook"],
    )
    supabase.table("video_tasks").update(
        {
            "talking_video_url": avatar.get("talking_video_url"),
            "heygen_video_id": avatar.get("video_id") or task.get("heygen_video_id") or "",
        }
    ).eq("id", task_id).execute()
    log_task(supabase, task_id=task_id, level="info", message="Avatar step completed", data=avatar)

    update_task_status(supabase, task_id, "rendering")
    final_video_url = await render_product_video(
        supabase,
        product_name=task["product_name"],
        image_url=task["image_url"],
        audio_url=tts_result["audio_url"],
        subtitle_text=script_package["subtitle_text"],
        watermark=limits["watermark"],
        max_seconds=limits["max_seconds"],
    )
    supabase.table("video_tasks").update(
        {
            "result_video_url": final_video_url,
            "status": "success",
            "subtitle_status": "completed",
        }
    ).eq("id", task_id).execute()
    try:
        supabase.table("task_queue").update({"status": "success"}).eq("task_id", task_id).execute()
    except Exception:
        pass
    log_task(supabase, task_id=task_id, level="info", message="Pipeline success", data={"final_video_url": final_video_url})
    return {"final_video_url": final_video_url}
