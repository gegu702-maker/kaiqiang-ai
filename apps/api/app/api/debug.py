from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter

from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.storage import upload_public_bytes

router = APIRouter(tags=["debug"])

REQUIRED_BUCKETS = ["images", "voices", "cloned", "videos", "subtitles"]


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
    return {
        "supabase_url_configured": bool(settings.supabase_url and settings.supabase_url != "https://example.supabase.co"),
        "supabase_url_host": settings.supabase_url.replace("https://", "").split("/")[0] if settings.supabase_url else "",
        "supabase_service_role_key_configured": bool(settings.supabase_service_role_key),
        "public_site_url": settings.public_site_url,
        "web_origin": settings.web_origin,
        "cors_origins": settings.allowed_origins,
    }
