from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException
from supabase import Client

from app.core.config import settings
from app.services.billing import assert_voice_clone_allowed


class VoiceCloneProvider:
    async def create_voice(self, *, name: str, sample_audio_url: str) -> dict:
        provider = settings.voice_clone_provider.lower()
        if provider == "mock":
            return {
                "provider": "mock",
                "voice_id": f"mock_voice_{uuid4().hex[:12]}",
                "status": "ready",
                "message": "Mock voice clone created. Replace provider with elevenlabs/minimax/fishaudio/openvoice when keys are ready.",
            }
        if provider in {"elevenlabs", "minimax", "fishaudio", "openvoice"}:
            return {
                "provider": provider,
                "voice_id": f"{provider}_pending_{uuid4().hex[:12]}",
                "status": "pending",
                "message": f"{provider} provider interface reserved. Add provider implementation to enable real cloning.",
            }
        raise HTTPException(status_code=400, detail=f"Unsupported VOICE_CLONE_PROVIDER: {settings.voice_clone_provider}")


def assert_clone_owner(supabase: Client, *, user_id: str, voice_clone_id: str) -> dict:
    result = (
        supabase.table("voice_clones")
        .select("*")
        .eq("id", voice_clone_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Voice clone not found.")
    clone = result.data[0]
    if clone.get("status") not in {"ready", "completed"}:
        raise HTTPException(status_code=400, detail="Voice clone is not ready.")
    return clone


def assert_user_can_clone(supabase: Client, *, user_id: str, email: str) -> None:
    assert_voice_clone_allowed(supabase, user_id=user_id, email=email)
