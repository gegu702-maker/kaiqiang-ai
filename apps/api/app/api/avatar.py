from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.billing import assert_generation_quota, log_generation_usage
from app.services.autodl_client import ensure_gpu_ready
from app.services.musetalk_client import check_musetalk_health, generate_avatar_video_with_musetalk
from app.services.storage import upload_public_file
from app.services.tts import synthesize_speech_to_storage

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
    background_tasks: BackgroundTasks,
    video_file: UploadFile = File(...),
    audio_file: UploadFile | None = File(None),
    script_text: str | None = Form(None),
    voice_type: str | None = Form(None),
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    task = None
    text = (script_text or "").strip()
    try:
        if audio_file is None and not text:
            raise HTTPException(status_code=400, detail="请上传口播音频，或输入文案用于生成语音。")
        assert_generation_quota(supabase, user_id=user["id"], email=user["email"])
        logger.info("Avatar request accepted user_id=%s has_audio=%s has_text=%s", user["id"], audio_file is not None, bool(text))
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
        logger.info("Avatar input video uploaded user_id=%s video_url=%s", user["id"], video_url)
        if audio_file is not None:
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
            logger.info("Avatar input audio uploaded user_id=%s audio_url=%s", user["id"], audio_url)
        else:
            logger.info("Avatar TTS started user_id=%s text_length=%s voice_type=%s", user["id"], len(text), voice_type or settings.volcengine_tts_voice_type)
            tts_result = await synthesize_speech_to_storage(
                supabase,
                text=text,
                folder="avatar-inputs/tts",
                voice_type=voice_type,
            )
            audio_url = tts_result["audio_url"]
            logger.info(
                "Avatar TTS completed user_id=%s provider=%s voice_type=%s duration=%s audio_url=%s",
                user["id"],
                tts_result.get("provider"),
                tts_result.get("voice_type"),
                tts_result.get("duration"),
                audio_url,
            )
        task = _create_avatar_task(supabase, user["id"], video_url, audio_url)
        logger.info("Avatar task queued task_id=%s user_id=%s", task["id"], user["id"])
        background_tasks.add_task(_process_avatar_task, task["id"], user["id"], video_url, audio_url)
        return {
            "success": True,
            "status": "queued",
            "task": _serialize_avatar_task(task),
            "task_id": task["id"],
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


async def _process_avatar_task(task_id: str, user_id: str, video_url: str, audio_url: str) -> None:
    supabase = get_supabase()

    def update_stage(stage: str) -> None:
        logger.info("Avatar task stage task_id=%s stage=%s", task_id, stage)
        _update_avatar_task(supabase, task_id, {"progress_stage": stage})

    logger.info("Avatar MuseTalk task started task_id=%s video_url=%s audio_url=%s", task_id, video_url, audio_url)
    try:
        logger.info("Avatar GPU readiness check started task_id=%s", task_id)
        await ensure_gpu_ready(update_stage)
        logger.info("Avatar GPU ready task_id=%s", task_id)
        _update_avatar_task(supabase, task_id, {"status": "running", "progress_stage": "video_generating"})
        logger.info("Avatar MuseTalk generation started task_id=%s", task_id)
        result_url = await generate_avatar_video_with_musetalk(
            supabase,
            video_url=video_url,
            audio_url=audio_url,
            task_id=task_id,
        )
        _update_avatar_task(
            supabase,
            task_id,
            {
                "status": "completed",
                "progress_stage": "completed",
                "result_url": result_url,
                "last_gpu_used_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info("Avatar result uploaded task_id=%s result_video_url=%s", task_id, result_url)
        log_generation_usage(supabase, user_id=user_id, avatar_task_id=task_id)
        logger.info("Avatar MuseTalk task completed task_id=%s result_url=%s", task_id, result_url)
    except HTTPException as error:
        logger.exception("Avatar MuseTalk task failed task_id=%s detail=%s", task_id, error.detail)
        _safe_fail_task(supabase, task_id, str(error.detail))
    except Exception as error:
        logger.exception("Avatar MuseTalk task failed task_id=%s", task_id)
        _safe_fail_task(supabase, task_id, str(error))


@router.get("/tasks")
def list_avatar_tasks(
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    user = get_authenticated_user(supabase, token)
    response = (
        supabase.table("avatar_tasks")
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    return [_serialize_avatar_task(item) for item in response.data or []]


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
    return _serialize_avatar_task(task)


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


def _serialize_avatar_task(task: dict) -> dict:
    result_url = task.get("result_url") or task.get("result_video_url")
    return {
        **task,
        "result_url": result_url,
        "result_video_url": result_url,
    }
