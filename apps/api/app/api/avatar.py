from __future__ import annotations

import ast
import asyncio
import logging
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.billing import assert_generation_quota, log_generation_usage
from app.services.autodl_client import ensure_gpu_ready
from app.services.avatar_template_videos import get_dynamic_template_video_url
from app.services.avatar_templates import get_avatar_template
from app.services.avatar_video_quality import check_avatar_video_quality
from app.services.musetalk_client import check_musetalk_health, generate_avatar_video_with_musetalk
from app.services.storage import upload_public_file
from app.services.tts import synthesize_speech_to_storage
from app.services.tts.voice_registry import DEFAULT_TTS_LANGUAGE, get_language_config, normalize_tts_language, serialize_voice_registry, validate_tts_voice

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


class TemplateAvatarGenerateRequest(BaseModel):
    script_text: str | None = None
    text: str | None = None
    audio_url: str | None = None
    language: str = DEFAULT_TTS_LANGUAGE
    voice: str | None = None
    voice_type: str | None = None
    avatar_template_id: str = Field(..., min_length=1)
    speed_ratio: float = Field(default=1.0, ge=0.5, le=2.0)
    volume_ratio: float = 1.0
    pitch_ratio: float = 1.0


class TTSPreviewRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1200)
    language: str = DEFAULT_TTS_LANGUAGE
    voice: str | None = None
    voice_type: str | None = None
    speed: float | None = None
    speed_ratio: float | None = None


@router.get("/health")
async def avatar_health() -> dict:
    return {
        "status": "ok",
        "musetalk": await check_musetalk_health(),
    }


@router.post("/video-quality-check")
async def check_avatar_video_upload_quality(
    video_file: UploadFile = File(...),
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    get_authenticated_user(supabase, token)
    filename = video_file.filename or "upload"
    extension = Path(filename).suffix.lower()
    content_type = video_file.content_type or "application/octet-stream"

    if extension not in VIDEO_EXTENSIONS or content_type not in VIDEO_TYPES:
        return {
            "success": True,
            "grade": "C",
            "reasons": [
                {
                    "code": "unsupported_format",
                    "severity": "blocking",
                    "message": "当前视频格式暂不支持，请上传 MP4、MOV 或 WebM。",
                }
            ],
            "metrics": {
                "duration_seconds": None,
                "width": None,
                "height": None,
                "fps": None,
                "codec": None,
                "format": extension.lstrip(".") or content_type,
            },
        }

    content = await video_file.read()
    if len(content) > 120 * MB:
        raise HTTPException(status_code=413, detail="视频文件过大，请上传 120MB 以内的视频。")

    with tempfile.TemporaryDirectory(prefix="avatar-video-quality-") as temp_dir:
        temp_path = Path(temp_dir) / f"input{extension}"
        temp_path.write_bytes(content)
        return await asyncio.to_thread(check_avatar_video_quality, temp_path)


@router.get("/tts-voices")
def list_tts_voices() -> dict:
    return {
        "default_language": DEFAULT_TTS_LANGUAGE,
        "languages": serialize_voice_registry(),
    }


@router.post("/tts-preview")
async def generate_tts_preview(
    payload: TTSPreviewRequest,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    selected_voice_type = payload.voice or payload.voice_type
    selected_speed = payload.speed if payload.speed is not None else payload.speed_ratio
    speed_ratio = selected_speed if selected_speed is not None else 1.0
    if speed_ratio < 0.5 or speed_ratio > 2.0:
        raise HTTPException(status_code=400, detail="speed must be between 0.5 and 2.0")
    logger.info(
        "Avatar TTS preview started user_id=%s text_length=%s language=%s voice_type=%s",
        user["id"],
        len(payload.text),
        payload.language,
        selected_voice_type,
    )
    result = await synthesize_speech_to_storage(
        supabase,
        text=payload.text,
        folder="avatar/tts-preview",
        language=payload.language,
        voice_type=selected_voice_type,
        speed_ratio=speed_ratio,
    )
    return {
        "success": True,
        "audio_url": result["audio_url"],
        "duration": result.get("duration", 0),
        "provider": result["provider"],
        "language": result.get("language") or normalize_tts_language(payload.language),
        "voice_type": result.get("voice_type") or selected_voice_type,
    }


@router.post("/template-generate")
async def generate_template_avatar_video(
    payload: TemplateAvatarGenerateRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    text = (payload.script_text or payload.text or "").strip()
    audio_url = (payload.audio_url or "").strip()
    template_id = payload.avatar_template_id.strip()
    template = get_avatar_template(template_id)
    template_video_url = get_dynamic_template_video_url(template.id)
    selected_voice_type = payload.voice or payload.voice_type or template.default_voice_type

    if not audio_url and not text:
        raise HTTPException(status_code=400, detail="请提供 audio_url，或输入文案用于生成语音。")

    assert_generation_quota(supabase, user_id=user["id"], email=user["email"])

    if not audio_url:
        selected_voice = validate_tts_voice(payload.language, selected_voice_type)
        selected_language = selected_voice.language
        try:
            logger.info(
                "Template avatar TTS started user_id=%s template=%s text_length=%s language=%s voice_type=%s",
                user["id"],
                template.id,
                len(text),
                selected_language or "default",
                selected_voice_type,
            )
            tts_result = await synthesize_speech_to_storage(
                supabase,
                text=text,
                folder="avatar/template-generate/tts",
                language=selected_language,
                voice_type=selected_voice.id,
                speed_ratio=payload.speed_ratio,
                volume_ratio=payload.volume_ratio,
                pitch_ratio=payload.pitch_ratio,
            )
            audio_url = tts_result["audio_url"]
        except HTTPException:
            raise
        except Exception as error:
            logger.exception("Template avatar TTS failed user_id=%s template=%s", user["id"], template.id)
            raise HTTPException(status_code=502, detail=str(error)) from error

    task = _create_avatar_task(supabase, user["id"], template_video_url, audio_url)
    logger.info(
        "Template avatar task queued task_id=%s user_id=%s template=%s template_video_url=%s audio_url=%s",
        task["id"],
        user["id"],
        template.id,
        template_video_url,
        audio_url,
    )
    background_tasks.add_task(_process_avatar_task, task["id"], user["id"], template_video_url, audio_url, text)
    return {
        "success": True,
        "status": "queued",
        "task": _serialize_avatar_task(task),
        "task_id": task["id"],
        "audio_url": audio_url,
        "avatar_template_id": template.id,
        "avatar_template_name": template.name,
    }


@router.post("/generate")
async def generate_avatar_video(
    background_tasks: BackgroundTasks,
    video_file: UploadFile = File(...),
    audio_file: UploadFile | None = File(None),
    script_text: str | None = Form(None),
    language: str = Form(DEFAULT_TTS_LANGUAGE),
    voice: str | None = Form(None),
    voice_type: str | None = Form(None),
    speed_ratio: float = Form(1.0),
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
            selected_voice_type = voice or voice_type
            logger.info(
                "Avatar TTS started user_id=%s text_length=%s language=%s voice_type=%s",
                user["id"],
                len(text),
                language,
                selected_voice_type or settings.volcengine_tts_voice_type,
            )
            tts_result = await synthesize_speech_to_storage(
                supabase,
                text=text,
                folder="avatar-inputs/tts",
                language=language,
                voice_type=selected_voice_type,
                speed_ratio=speed_ratio,
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
        background_tasks.add_task(_process_avatar_task, task["id"], user["id"], video_url, audio_url, text)
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


async def _process_avatar_task(task_id: str, user_id: str, video_url: str, audio_url: str, script_text: str | None = None) -> None:
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
        result = await generate_avatar_video_with_musetalk(
            supabase,
            video_url=video_url,
            audio_url=audio_url,
            task_id=task_id,
            script_text=script_text,
        )
        result_url = result.result_url
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
        logger.info("Avatar result uploaded task_id=%s result_video_url=%s subtitle_status=%s", task_id, result_url, result.subtitle_status)
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
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    return [_serialize_avatar_task(item) for item in response.data or []]


@router.delete("/tasks/{task_id}")
def delete_avatar_task(
    task_id: str,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    task = _get_owned_active_avatar_task(supabase, task_id, user["id"])
    if task.get("status") in {"queued", "running"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "avatar_task_still_generating",
                "message": "任务仍在生成中，暂不能删除。",
            },
        )
    response = (
        supabase.table("avatar_tasks")
        .update({"deleted_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", task_id)
        .eq("user_id", user["id"])
        .is_("deleted_at", "null")
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Avatar task not found")
    return {"success": True, "status": "deleted", "task_id": task_id}


@router.get("/tasks/{task_id}")
def get_avatar_task(
    task_id: str,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    return _serialize_avatar_task(_get_owned_active_avatar_task(supabase, task_id, user["id"]))


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


def _get_owned_active_avatar_task(supabase: Client, task_id: str, user_id: str) -> dict:
    response = (
        supabase.table("avatar_tasks")
        .select("*")
        .eq("id", task_id)
        .eq("user_id", user_id)
        .is_("deleted_at", "null")
        .maybe_single()
        .execute()
    )
    task = response.data
    if not task:
        raise HTTPException(status_code=404, detail="Avatar task not found")
    return task


def _safe_fail_task(supabase: Client, task_id: str, message: str) -> None:
    try:
        supabase.table("avatar_tasks").update({"status": "failed", "progress_stage": "failed", "error_message": _compact_error_message(message)}).eq("id", task_id).execute()
    except Exception:
        logger.exception("Failed to mark avatar task failed")


def _normalize_tts_language(language: str | None) -> str | None:
    if not (language or "").strip():
        return None
    normalized = normalize_tts_language(language)
    get_language_config(normalized)
    return normalized


def _validate_template_tts_voice(language: str, voice_type: str) -> None:
    try:
        validate_tts_voice(language, voice_type)
    except HTTPException as error:
        if normalize_tts_language(language) == "en-US" and "coming soon" in str(error.detail).lower():
            raise HTTPException(status_code=400, detail="English TTS voices are not configured yet.") from error
        raise


def _compact_error_message(message: str) -> str:
    try:
        parsed = ast.literal_eval(message)
    except (SyntaxError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        primary = parsed.get("message_zh") or parsed.get("message") or parsed.get("code")
        if primary:
            code = parsed.get("code")
            suffix = f" ({code})" if code and code not in str(primary) else ""
            return f"{primary}{suffix}"[:500]
    return message[:500]


def _serialize_avatar_task(task: dict) -> dict:
    result_url = task.get("result_url") or task.get("result_video_url")
    subtitle_status = task.get("subtitle_status") or "unknown"
    return {
        **task,
        "result_url": result_url,
        "result_video_url": result_url,
        "subtitle_status": subtitle_status,
    }
