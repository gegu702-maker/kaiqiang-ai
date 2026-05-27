from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from postgrest.exceptions import APIError
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.storage import upload_public_file
from app.services.voice_clone_provider import VoiceCloneProvider, assert_user_can_clone

router = APIRouter(prefix="/voice-clone", tags=["voice-clone"])

VOICE_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".mpeg"}
VOICE_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/x-mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/m4a",
    "audio/x-m4a",
    "audio/mp4",
    "audio/aac",
    "audio/x-aac",
    "audio/mp4a-latm",
    "video/mp4",
    "application/octet-stream",
}
MB = 1024 * 1024


@router.post("/upload")
async def upload_voice_sample(
    name: str = Form(...),
    sample_audio: UploadFile = File(...),
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    assert_user_can_clone(supabase, user_id=user["id"], email=user["email"])
    sample_audio_url = await upload_public_file(
        supabase,
        settings.supabase_voice_bucket,
        sample_audio,
        "voice-clone-samples",
        allowed_extensions=VOICE_EXTENSIONS,
        allowed_content_types=VOICE_TYPES,
        max_bytes=20 * MB,
        allowed_format_label="mp3, wav, m4a",
    )
    result = supabase.table("voice_clones").insert(
        {
            "user_id": user["id"],
            "provider": settings.voice_clone_provider,
            "name": name,
            "sample_audio_url": sample_audio_url,
            "status": "uploaded",
        }
    ).execute()
    return result.data[0]


@router.post("/create")
async def create_voice_clone(
    voice_clone_id: str = Form(...),
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    assert_user_can_clone(supabase, user_id=user["id"], email=user["email"])
    existing = (
        supabase.table("voice_clones")
        .select("*")
        .eq("id", voice_clone_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Voice clone not found.")
    clone = existing.data[0]
    provider_result = await VoiceCloneProvider().create_voice(
        name=clone["name"],
        sample_audio_url=clone["sample_audio_url"],
    )
    updated = supabase.table("voice_clones").update(
        {
            "provider": provider_result["provider"],
            "voice_id": provider_result["voice_id"],
            "status": provider_result["status"],
        }
    ).eq("id", voice_clone_id).execute()
    if provider_result["status"] in {"ready", "completed"}:
        supabase.table("profiles").update(
            {"default_voice_id": provider_result["voice_id"], "voice_clone_enabled": True}
        ).eq("id", user["id"]).execute()
    return updated.data[0]


@router.get("/list")
def list_voice_clones(
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    user = get_authenticated_user(supabase, token)
    try:
        result = (
            supabase.table("voice_clones")
            .select("*")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        return result.data
    except APIError:
        return []


@router.delete("/{voice_clone_id}")
def delete_voice_clone(
    voice_clone_id: str,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    supabase.table("voice_clones").delete().eq("id", voice_clone_id).eq("user_id", user["id"]).execute()
    return {"ok": True}
