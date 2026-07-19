from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx
from fastapi import HTTPException
from supabase import Client

from app.core.config import settings
from app.services.storage import upload_public_bytes
from app.services.tts.volcengine_tts import VolcengineTTSProvider
from app.services.tts.voice_registry import DEFAULT_TTS_LANGUAGE, resolve_voice


async def synthesize_speech_to_storage(
    supabase: Client,
    *,
    text: str,
    voice_clone: dict | None = None,
    folder: str = "tts",
    language: str | None = DEFAULT_TTS_LANGUAGE,
    voice_type: str | None = None,
    legacy_provider_voice_id: str | None = None,
    speed_ratio: float = 1.0,
    volume_ratio: float = 1.0,
    pitch_ratio: float = 1.0,
) -> dict:
    if speed_ratio < 0.5 or speed_ratio > 2.0:
        raise HTTPException(status_code=400, detail="TTS speed_ratio must be between 0.5 and 2.0.")
    if volume_ratio <= 0 or pitch_ratio <= 0:
        raise HTTPException(status_code=400, detail="TTS volume_ratio and pitch_ratio must be greater than 0.")

    provider = settings.voice_clone_provider.lower()
    extension = ".mp3"
    content_type = "audio/mpeg"
    provider_name = "unknown"
    resolved_voice = resolve_voice(voice_type, language, legacy_provider_voice_id=legacy_provider_voice_id)
    selected_voice_type = resolved_voice.resolved_key

    if provider == "volcengine":
        result = await VolcengineTTSProvider().synthesize(
            text=text,
            language=language,
            voice_type=resolved_voice.provider_voice_id,
            speed_ratio=speed_ratio,
            volume_ratio=volume_ratio,
            pitch_ratio=pitch_ratio,
        )
        audio = result["audio_bytes"]
        extension = result["extension"]
        content_type = result["content_type"]
        provider_name = result["provider"]
    elif voice_clone and voice_clone.get("provider") == "elevenlabs" and voice_clone.get("voice_id"):
        audio = await _elevenlabs_tts(text, voice_id=voice_clone["voice_id"])
        provider_name = "elevenlabs"
    elif settings.elevenlabs_api_key and settings.elevenlabs_voice_id:
        audio = await _elevenlabs_tts(text, voice_id=settings.elevenlabs_voice_id)
        provider_name = "elevenlabs"
    elif settings.openai_api_key:
        audio = await _openai_tts(text)
        provider_name = "openai"
    else:
        raise HTTPException(status_code=503, detail="配音服务尚未完成配置。")

    audio_url = upload_public_bytes(
        supabase,
        settings.supabase_voice_bucket,
        audio,
        folder,
        extension,
        content_type,
    )
    duration = probe_audio_duration(audio)
    return {
        "audio_url": audio_url,
        "duration": duration,
        "audio_bytes": audio,
        "provider": provider_name,
        "language": language,
        "voice": selected_voice_type,
        "used_fallback": resolved_voice.used_fallback,
        "content_type": content_type,
    }


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
        raise HTTPException(status_code=502, detail=_format_tts_error("OpenAI", response.status_code, response.text))
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
        raise HTTPException(status_code=502, detail=_format_tts_error("ElevenLabs", response.status_code, response.text))
    return response.content


def _format_tts_error(provider: str, status_code: int, body: str) -> str:
    if status_code in {401, 403}:
        return (
            f"{provider} TTS 权限不足或 API Key 无效。请检查账号是否允许 API 调用、所选 voice 是否可用，"
            f"以及免费试用版是否限制 voice clone / TTS。返回：{body[:500]}"
        )
    if status_code in {402, 429}:
        return (
            f"{provider} TTS 额度不足、免费试用版限制或请求频率受限。请检查 credits、订阅套餐和并发限制。"
            f" 返回：{body[:500]}"
        )
    return f"{provider} TTS failed ({status_code}): {body[:800]}"


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
