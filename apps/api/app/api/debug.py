from datetime import datetime, timezone
import hashlib
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.supabase import get_supabase
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
