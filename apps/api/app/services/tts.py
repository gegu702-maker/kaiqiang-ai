from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
import shutil

import httpx
from fastapi import HTTPException
from supabase import Client

from app.core.config import settings
from app.services.storage import upload_public_bytes


async def synthesize_speech_to_storage(
    supabase: Client,
    *,
    text: str,
    voice_clone: dict | None = None,
    folder: str = "tts",
) -> dict:
    if voice_clone and voice_clone.get("provider") == "elevenlabs" and voice_clone.get("voice_id"):
        audio = await _elevenlabs_tts(text, voice_id=voice_clone["voice_id"])
    elif settings.elevenlabs_api_key and settings.elevenlabs_voice_id:
        audio = await _elevenlabs_tts(text, voice_id=settings.elevenlabs_voice_id)
    elif settings.openai_api_key:
        audio = await _openai_tts(text)
    else:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY 或 ELEVENLABS_API_KEY 未配置，无法生成真实 TTS。")

    audio_url = upload_public_bytes(
        supabase,
        settings.supabase_voice_bucket,
        audio,
        folder,
        ".mp3",
        "audio/mpeg",
    )
    duration = probe_audio_duration(audio)
    return {"audio_url": audio_url, "duration": duration, "audio_bytes": audio}


async def _openai_tts(text: str) -> bytes:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_tts_model,
                "voice": settings.openai_tts_voice,
                "input": text,
                "format": "mp3",
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"OpenAI TTS failed: {response.text}")
    return response.content


async def _elevenlabs_tts(text: str, *, voice_id: str) -> bytes:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": settings.elevenlabs_api_key},
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.8},
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"ElevenLabs TTS failed: {response.text}")
    return response.content


def probe_audio_duration(audio: bytes) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        candidate = settings.ffmpeg_path.replace("ffmpeg", "ffprobe")
        ffprobe = candidate if Path(candidate).exists() else "ffprobe"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "voice.mp3"
        path.write_bytes(audio)
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    try:
        return round(float(result.stdout.strip()), 2)
    except Exception:
        return 0.0
