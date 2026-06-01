from datetime import datetime, timezone
import hashlib
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.avatar_motion import get_avatar_motion_provider, liveportrait_configured, replicate_configured
from app.services.avatar_templates import avatar_template_public_url, get_avatar_template
from app.services.static_avatar_video import package_dynamic_avatar_video, render_static_avatar_video
from app.services.storage import upload_public_bytes
from app.services.tts import synthesize_speech_to_storage

router = APIRouter(tags=["debug"])

REQUIRED_BUCKETS = ["images", "voices", "cloned", "videos", "subtitles"]


class TTSTestRequest(BaseModel):
    text: str = Field(default="你好，我是凯强 AI 数字人", min_length=1)
    voice_type: str | None = None
    speed_ratio: float = 1.0
    volume_ratio: float = 1.0
    pitch_ratio: float = 1.0


class StaticAvatarVideoTestRequest(TTSTestRequest):
    avatar_template_id: str | None = None


class LivePortraitTestRequest(StaticAvatarVideoTestRequest):
    driving_video_url: str | None = None


@router.get("/debug/supabase")
def debug_supabase() -> dict:
    supabase = get_supabase()
    result: dict = {
        "database": False,
        "storage": False,
        "buckets": {},
        "test_upload_url": None,
        "video_tasks_write": False,
        "generated_sql": None,
        "errors": [],
    }

    try:
        existing = {bucket.name for bucket in supabase.storage.list_buckets()}
        for bucket in REQUIRED_BUCKETS:
            if bucket not in existing:
                supabase.storage.create_bucket(bucket, options={"public": True})
            result["buckets"][bucket] = True
        result["storage"] = True
    except Exception as error:
        result["errors"].append(f"storage: {error}")

    try:
        test_content = f"Supabase storage test {datetime.now(timezone.utc).isoformat()}".encode("utf-8")
        result["test_upload_url"] = upload_public_bytes(
            supabase,
            "voices",
            test_content,
            "debug",
            ".txt",
            "text/plain; charset=utf-8",
        )
    except Exception as error:
        result["errors"].append(f"upload: {error}")

    try:
        supabase.table("video_tasks").select("id").limit(1).execute()
        result["database"] = True
    except Exception as error:
        result["errors"].append(f"database: {error}")
        schema_path = Path(__file__).resolve().parents[4] / "supabase" / "schema.sql"
        result["generated_sql"] = str(schema_path)
        result["sql_instruction"] = "Run this SQL file in Supabase SQL Editor, then call /debug/supabase again."

    if result["database"]:
        try:
            payload = {
                "user_email": "debug@example.com",
                "product_name": "Supabase Debug Task",
                "script": "This is a Supabase debug task.",
                "language": "en",
                "image_url": result["test_upload_url"] or "https://example.com/image.png",
                "avatar_id": "emily",
                "voice_url": result["test_upload_url"] or "https://example.com/voice.txt",
                "tts_language": "en",
                "tts_voice_name": "minimax_en_female",
                "admin_notes": "Created by /debug/supabase",
                "status": "pending",
                "subtitle_status": "pending",
                "cosyvoice_status": "pending",
            }
            inserted = supabase.table("video_tasks").insert(payload).execute()
            inserted_id = inserted.data[0]["id"]
            result["video_tasks_write"] = True
            result["debug_task_id"] = inserted_id
        except Exception as error:
            result["errors"].append(f"video_tasks_write: {error}")

    return result


@router.get("/debug/config")
def debug_config() -> dict:
    admin_key = settings.admin_api_key.strip()
    volcengine_tts_configured = all(
        [
            settings.volcengine_tts_app_id.strip(),
            settings.volcengine_tts_access_token.strip(),
            settings.volcengine_tts_cluster.strip(),
            settings.volcengine_tts_voice_type.strip(),
        ]
    )
    return {
        "supabase_url_configured": bool(settings.supabase_url and settings.supabase_url != "https://example.supabase.co"),
        "supabase_url_host": settings.supabase_url.replace("https://", "").split("/")[0] if settings.supabase_url else "",
        "supabase_service_role_key_configured": bool(settings.supabase_service_role_key),
        "public_site_url": settings.public_site_url,
        "web_origin": settings.web_origin,
        "cors_origins": settings.allowed_origins,
        "openai_api_key_configured": bool(settings.openai_api_key),
        "openai_tts_model": settings.openai_tts_model,
        "deepseek_api_key_configured": bool(settings.deepseek_api_key),
        "gemini_api_key_configured": bool(settings.gemini_api_key),
        "dashscope_api_key_configured": bool(settings.dashscope_api_key),
        "llm_provider": settings.llm_provider,
        "elevenlabs_api_key_configured": bool(settings.elevenlabs_api_key),
        "elevenlabs_voice_id_configured": bool(settings.elevenlabs_voice_id),
        "volcengine_tts_app_id_configured": bool(settings.volcengine_tts_app_id),
        "volcengine_tts_access_token_configured": bool(settings.volcengine_tts_access_token),
        "volcengine_tts_cluster_configured": bool(settings.volcengine_tts_cluster),
        "volcengine_tts_cluster": settings.volcengine_tts_cluster,
        "volcengine_tts_voice_type_configured": bool(settings.volcengine_tts_voice_type),
        "volcengine_tts_voice_type": settings.volcengine_tts_voice_type,
        "volcengine_tts_configured": volcengine_tts_configured,
        "volcengine_tts_endpoint": settings.volcengine_tts_endpoint,
        "heygen_api_key_configured": bool(settings.heygen_api_key),
        "heygen_avatar_id_configured": bool(settings.heygen_avatar_id),
        "heygen_voice_id_configured": bool(settings.heygen_voice_id),
        "voice_clone_provider": settings.voice_clone_provider,
        "avatar_motion_provider": settings.avatar_motion_provider,
        "liveportrait_api_base_url_configured": bool(settings.liveportrait_api_base_url.strip()),
        "liveportrait_api_key_configured": bool(settings.liveportrait_api_key.strip()),
        "liveportrait_default_driving_video_url_configured": bool(settings.liveportrait_default_driving_video_url.strip()),
        "liveportrait_api_configured": liveportrait_configured(),
        "replicate_api_configured": replicate_configured(),
        "replicate_api_token_configured": bool(settings.replicate_api_token.strip()),
        "replicate_liveportrait_model": settings.replicate_liveportrait_model,
        "liveportrait_default_driving_video_configured": bool(settings.liveportrait_default_driving_video_url.strip()),
        "musetalk_api_base_url_configured": bool(settings.musetalk_api_base_url.strip()),
        "muse_talk_api_base_url_configured": bool(settings.musetalk_api_base_url.strip()),
        "musetalk_api_key_configured": bool(settings.musetalk_api_key.strip()),
        "musetalk_timeout_seconds": settings.musetalk_timeout_seconds,
        "autodl_api_token_configured": bool(settings.autodl_api_token.strip()),
        "autodl_instance_id_configured": bool(settings.autodl_instance_id.strip()),
        "autodl_region": settings.autodl_region,
        "autodl_api_base_url": settings.autodl_api_base_url,
        "autodl_start_timeout_seconds": settings.autodl_start_timeout_seconds,
        "gpu_idle_shutdown_minutes": settings.gpu_idle_shutdown_minutes,
        "enable_task_worker": settings.enable_task_worker,
        "ffmpeg_path": settings.ffmpeg_path,
        "admin_api_key_configured": bool(admin_key),
        "admin_api_key_fingerprint": hashlib.sha256(admin_key.encode("utf-8")).hexdigest()[:12] if admin_key else "",
    }


@router.post("/api/debug/tts-test")
async def debug_tts_test(payload: TTSTestRequest) -> dict:
    supabase = get_supabase()
    result = await synthesize_speech_to_storage(
        supabase,
        text=payload.text,
        folder="debug/tts-test",
        voice_type=payload.voice_type,
        speed_ratio=payload.speed_ratio,
        volume_ratio=payload.volume_ratio,
        pitch_ratio=payload.pitch_ratio,
    )
    return {
        "success": True,
        "audio_url": result["audio_url"],
        "provider": result["provider"],
        "voice_type": result.get("voice_type") or payload.voice_type or settings.volcengine_tts_voice_type,
    }


@router.post("/api/debug/avatar-video-test")
async def debug_avatar_video_test(payload: StaticAvatarVideoTestRequest) -> dict:
    template = get_avatar_template(payload.avatar_template_id)
    supabase = get_supabase()
    selected_voice_type = payload.voice_type or template.voice_type
    tts_result = await synthesize_speech_to_storage(
        supabase,
        text=payload.text,
        folder="debug/avatar-video/tts",
        voice_type=selected_voice_type,
        speed_ratio=payload.speed_ratio,
        volume_ratio=payload.volume_ratio,
        pitch_ratio=payload.pitch_ratio,
    )
    video_url = await render_static_avatar_video(
        supabase,
        audio_url=tts_result["audio_url"],
        subtitle_text=payload.text,
        avatar_image_url=avatar_template_public_url(template),
        duration=tts_result.get("duration"),
    )
    return {
        "success": True,
        "video_url": video_url,
        "audio_url": tts_result["audio_url"],
        "provider": tts_result["provider"],
        "voice_type": tts_result.get("voice_type") or selected_voice_type or settings.volcengine_tts_voice_type,
        "avatar_template_id": template.id,
        "avatar_template_name": template.name,
    }


@router.post("/api/debug/liveportrait-test")
async def debug_liveportrait_test(payload: LivePortraitTestRequest) -> dict:
    template = get_avatar_template(payload.avatar_template_id)
    supabase = get_supabase()
    selected_voice_type = payload.voice_type or template.default_voice_type
    tts_result = await synthesize_speech_to_storage(
        supabase,
        text=payload.text,
        folder="debug/liveportrait/tts",
        voice_type=selected_voice_type,
        speed_ratio=payload.speed_ratio,
        volume_ratio=payload.volume_ratio,
        pitch_ratio=payload.pitch_ratio,
    )
    source_image_url = avatar_template_public_url(template)
    provider = get_avatar_motion_provider()
    if provider is None:
        dynamic_avatar_video_url = await render_static_avatar_video(
            supabase,
            audio_url=tts_result["audio_url"],
            subtitle_text=payload.text,
            avatar_image_url=source_image_url,
            duration=tts_result.get("duration"),
        )
        motion_provider = "static"
    else:
        dynamic_avatar_video_url = await provider.generate_avatar_motion(
            source_image_url=source_image_url,
            audio_url=tts_result["audio_url"],
            driving_video_url=payload.driving_video_url,
            task_id=f"debug-liveportrait-{template.id}",
        )
        final_video_url = await package_dynamic_avatar_video(
            supabase,
            dynamic_video_url=dynamic_avatar_video_url,
            audio_url=tts_result["audio_url"],
            subtitle_text=payload.text,
            task_id=template.id,
            duration=tts_result.get("duration"),
        )
        motion_provider = settings.avatar_motion_provider
    if provider is None:
        final_video_url = dynamic_avatar_video_url

    return {
        "success": True,
        "audio_url": tts_result["audio_url"],
        "dynamic_avatar_video_url": dynamic_avatar_video_url,
        "final_video_url": final_video_url,
        "provider": motion_provider,
        "tts_provider": tts_result["provider"],
        "voice_type": tts_result.get("voice_type") or selected_voice_type,
        "avatar_template_id": template.id,
        "avatar_template_name": template.name,
        "avatar_motion_provider": motion_provider,
    }
