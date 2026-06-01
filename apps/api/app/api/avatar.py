from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.autodl_client import ensure_gpu_ready
from app.services.musetalk_client import check_musetalk_health, generate_avatar_video_with_musetalk
from app.services.storage import upload_public_file

router = APIRouter(prefix="/avatar", tags=["avatar"])
logger = logging.getLogger(__name__)

MB = 1024 * 1024
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}
VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm", "application/octet-stream"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac"}
AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/m4a",
    "audio/mp4",
    "audio/aac",
    "application/octet-stream",
}


@router.get("/health")
async def avatar_health() -> dict:
    return {
        "status": "ok",
        "musetalk": await check_musetalk_health(),
    }


@router.post("/generate")
async def generate_avatar_video(
    video_file: UploadFile = File(...),
    audio_file: UploadFile = File(...),
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    task = None
    try:
        video_url = await upload_public_file(
            supabase,
            settings.supabase_video_bucket,
            video_file,
            "avatar-inputs/video",
            allowed_extensions=VIDEO_EXTENSIONS,
            allowed_content_types=VIDEO_TYPES,
            max_bytes=120 * MB,
            allowed_format_label="mp4, mov, webm",
        )
        audio_url = await upload_public_file(
            supabase,
            settings.supabase_voice_bucket,
            audio_file,
            "avatar-inputs/audio",
            allowed_extensions=AUDIO_EXTENSIONS,
            allowed_content_types=AUDIO_TYPES,
            max_bytes=40 * MB,
            allowed_format_label="wav, mp3, m4a, aac",
        )
        task = _create_avatar_task(supabase, user["id"], video_url, audio_url)

        def update_stage(stage: str) -> None:
            _update_avatar_task(supabase, task["id"], {"progress_stage": stage})

        await ensure_gpu_ready(update_stage)
        _update_avatar_task(supabase, task["id"], {"status": "running", "progress_stage": "video_generating"})
        result_url = await generate_avatar_video_with_musetalk(
            supabase,
            video_url=video_url,
            audio_url=audio_url,
            task_id=task["id"],
        )
        task = _update_avatar_task(
            supabase,
            task["id"],
            {
                "status": "completed",
                "progress_stage": "completed",
                "result_url": result_url,
                "last_gpu_used_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "success": True,
            "task": task,
            "video_url": result_url,
        }
    except HTTPException as error:
        if task:
            _safe_fail_task(supabase, task["id"], str(error.detail))
        raise
    except Exception as error:
        logger.exception("Avatar video generation failed")
        if task:
            _safe_fail_task(supabase, task["id"], str(error))
        raise HTTPException(
            status_code=500,
            detail={
                "message": str(error),
                "type": error.__class__.__name__,
                "traceback": traceback.format_exc()[-6000:],
            },
        ) from error


@router.get("/tasks/{task_id}")
def get_avatar_task(
    task_id: str,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    response = supabase.table("avatar_tasks").select("*").eq("id", task_id).eq("user_id", user["id"]).maybe_single().execute()
    task = response.data
    if not task:
        raise HTTPException(status_code=404, detail="Avatar task not found")
    return task


def _create_avatar_task(supabase: Client, user_id: str, video_url: str, audio_url: str) -> dict:
    response = (
        supabase.table("avatar_tasks")
        .insert(
            {
                "user_id": user_id,
                "video_url": video_url,
                "audio_url": audio_url,
                "status": "queued",
                "progress_stage": "queued",
            }
        )
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create avatar task")
    return response.data[0]


def _update_avatar_task(supabase: Client, task_id: str, values: dict) -> dict:
    response = supabase.table("avatar_tasks").update(values).eq("id", task_id).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to update avatar task")
    return response.data[0]


def _safe_fail_task(supabase: Client, task_id: str, message: str) -> None:
    try:
        supabase.table("avatar_tasks").update({"status": "failed", "progress_stage": "failed", "error_message": message[:2000]}).eq("id", task_id).execute()
    except Exception:
        logger.exception("Failed to mark avatar task failed")
