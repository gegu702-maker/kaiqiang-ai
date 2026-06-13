from __future__ import annotations

import base64
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.core.config import settings


# TODO: Replace fallback voice_type values with provider-confirmed multilingual voices.
VOLCENGINE_DEFAULT_VOICE_TYPES = {
    "zh": lambda: settings.volcengine_tts_voice_type,
    "en": lambda: settings.volcengine_tts_voice_type,
    "ja": lambda: settings.volcengine_tts_voice_type,
    "ko": lambda: settings.volcengine_tts_voice_type,
    "es": lambda: settings.volcengine_tts_voice_type,
    "fr": lambda: settings.volcengine_tts_voice_type,
    "ru": lambda: settings.volcengine_tts_voice_type,
}


def get_default_volcengine_voice_type(locale: str) -> str:
    resolver = VOLCENGINE_DEFAULT_VOICE_TYPES.get(locale, VOLCENGINE_DEFAULT_VOICE_TYPES["en"])
    return resolver().strip()


class VolcengineTTSProvider:
    def __init__(
        self,
        *,
        app_id: str | None = None,
        access_token: str | None = None,
        cluster: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        self.app_id = (app_id if app_id is not None else settings.volcengine_tts_app_id).strip()
        self.access_token = (
            access_token if access_token is not None else settings.volcengine_tts_access_token
        ).strip()
        self.cluster = (cluster if cluster is not None else settings.volcengine_tts_cluster).strip()
        self.endpoint = (endpoint if endpoint is not None else settings.volcengine_tts_endpoint).strip()

    async def synthesize(
        self,
        *,
        text: str,
        voice_type: str | None = None,
        speed_ratio: float = 1.0,
        volume_ratio: float = 1.0,
        pitch_ratio: float = 1.0,
    ) -> dict:
        clean_text = text.strip()
        selected_voice = (voice_type or get_default_volcengine_voice_type("en")).strip()
        self._validate(selected_voice)

        payload = {
            "app": {
                "appid": self.app_id,
                "token": self.access_token,
                "cluster": self.cluster,
            },
            "user": {
                "uid": f"kaiqiang-{uuid4().hex}",
            },
            "audio": {
                "voice_type": selected_voice,
                "encoding": "mp3",
                "speed_ratio": speed_ratio,
                "volume_ratio": volume_ratio,
                "pitch_ratio": pitch_ratio,
            },
            "request": {
                "reqid": uuid4().hex,
                "text": clean_text,
                "text_type": "plain",
                "operation": "query",
            },
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer;{self.access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=_format_volcengine_error(response.status_code, response.text),
            )

        try:
            data = response.json()
        except ValueError as error:
            raise HTTPException(status_code=502, detail="Volcengine TTS returned non-JSON response.") from error

        code = data.get("code")
        if code not in {None, 0, 200, "0", "200", 3000, "3000"}:
            message = str(data.get("message") or data.get("msg") or data)[:1000]
            raise HTTPException(status_code=502, detail=_format_volcengine_api_error(message))

        audio_base64 = _find_audio_base64(data)
        if not audio_base64:
            raise HTTPException(status_code=502, detail=f"Volcengine TTS response missing audio data: {str(data)[:800]}")

        try:
            audio = base64.b64decode(audio_base64)
        except Exception as error:
            raise HTTPException(status_code=502, detail="Volcengine TTS audio data is not valid base64.") from error

        return {
            "audio_bytes": audio,
            "extension": ".mp3",
            "content_type": "audio/mpeg",
            "provider": "volcengine",
            "voice_type": selected_voice,
        }

    def _validate(self, voice_type: str) -> None:
        if not self.access_token:
            raise HTTPException(status_code=500, detail="VOLCENGINE_TTS_ACCESS_TOKEN missing")
        if not self.app_id:
            raise HTTPException(status_code=500, detail="VOLCENGINE_TTS_APP_ID missing")
        if not self.cluster:
            raise HTTPException(status_code=500, detail="VOLCENGINE_TTS_CLUSTER missing")
        if not voice_type:
            raise HTTPException(status_code=500, detail="VOLCENGINE_TTS_VOICE_TYPE missing")
        if not self.endpoint:
            raise HTTPException(status_code=500, detail="VOLCENGINE_TTS_ENDPOINT missing")


def _find_audio_base64(data: dict) -> str:
    direct = data.get("data")
    if isinstance(direct, str):
        return direct
    if isinstance(direct, dict):
        for key in ("audio", "audio_data", "data"):
            value = direct.get(key)
            if isinstance(value, str):
                return value
    for key in ("audio", "audio_data"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return ""


def _format_volcengine_api_error(message: str) -> str:
    lowered = message.lower()
    if "voice" in lowered and ("invalid" in lowered or "not" in lowered or "unsupported" in lowered):
        return f"Volcengine TTS voice_type invalid: {message}"
    if any(token in lowered for token in ["quota", "permission", "unauthorized", "forbidden", "balance", "credit"]):
        return f"Volcengine TTS quota/permission error: {message}"
    return f"Volcengine TTS failed: {message}"


def _format_volcengine_error(status_code: int, body: str) -> str:
    if status_code in {401, 403}:
        return f"Volcengine TTS quota/permission error: API permission denied or token invalid. 返回：{body[:500]}"
    if status_code in {402, 429}:
        return f"Volcengine TTS quota/permission error: quota, balance, or rate limit issue. 返回：{body[:500]}"
    if status_code == 400 and "voice" in body.lower():
        return f"Volcengine TTS voice_type invalid: {body[:500]}"
    return f"Volcengine TTS failed ({status_code}): {body[:800]}"
