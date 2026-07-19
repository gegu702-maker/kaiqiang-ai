from __future__ import annotations

import base64
import logging
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.services.tts.voice_registry import DEFAULT_TTS_LANGUAGE

logger = logging.getLogger(__name__)
PROVIDER_ERROR_DETAIL = "配音服务暂时不可用，请稍后重试。"


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
        language: str | None = DEFAULT_TTS_LANGUAGE,
        voice_type: str | None = None,
        speed_ratio: float = 1.0,
        volume_ratio: float = 1.0,
        pitch_ratio: float = 1.0,
    ) -> dict:
        clean_text = text.strip()
        selected_voice = (voice_type or "").strip()
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
            logger.warning("TTS provider request failed status_code=%s", response.status_code)
            raise HTTPException(status_code=502, detail=PROVIDER_ERROR_DETAIL)

        try:
            data = response.json()
        except ValueError as error:
            logger.warning("TTS provider returned an invalid response status_code=%s", response.status_code)
            raise HTTPException(status_code=502, detail=PROVIDER_ERROR_DETAIL) from error

        code = data.get("code")
        if code not in {None, 0, 200, "0", "200", 3000, "3000"}:
            logger.warning("TTS provider returned an application error code=%s", code)
            raise HTTPException(status_code=502, detail=PROVIDER_ERROR_DETAIL)

        audio_base64 = _find_audio_base64(data)
        if not audio_base64:
            logger.warning("TTS provider response did not contain audio data")
            raise HTTPException(status_code=502, detail=PROVIDER_ERROR_DETAIL)

        try:
            audio = base64.b64decode(audio_base64)
        except Exception as error:
            logger.warning("TTS provider returned invalid audio data")
            raise HTTPException(status_code=502, detail=PROVIDER_ERROR_DETAIL) from error

        return {
            "audio_bytes": audio,
            "extension": ".mp3",
            "content_type": "audio/mpeg",
            "provider": "volcengine",
            "language": language,
            "voice_type": selected_voice,
        }

    def _validate(self, voice_type: str) -> None:
        missing = []
        if not self.access_token:
            missing.append("credentials")
        if not self.app_id:
            missing.append("application")
        if not self.cluster:
            missing.append("cluster")
        if not voice_type:
            missing.append("voice_mapping")
        if not self.endpoint:
            missing.append("endpoint")
        if missing:
            logger.error("TTS provider configuration incomplete missing_categories=%s", ",".join(missing))
            raise HTTPException(status_code=503, detail="配音服务尚未完成配置。")


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


# Provider response bodies are intentionally never exposed through HTTP details.
