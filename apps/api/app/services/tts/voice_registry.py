from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TTS_LANGUAGE = "zh-CN"
DEFAULT_VOICE_KEY = "zh_female_default"

LEGACY_PROVIDER_VOICE_COMPATIBILITY = {
    "BV001_streaming": "BV001_streaming",
    "BV002_streaming": "BV002_streaming",
}

VOICE_LANGUAGE_MAP = {
    "zh_female_default": "zh-CN",
    "zh_male_default": "zh-CN",
    "zh_warm_female": "zh-CN",
    "zh_steady_male": "zh-CN",
    "zh_energetic_female": "zh-CN",
    "zh_knowledge_host": "zh-CN",
    "zh_business_narration": "zh-CN",
    "zh_casual_spoken": "zh-CN",
}

VOICE_SETTING_MAP = {
    "zh_female_default": "volcengine_voice_zh_female_default",
    "zh_male_default": "volcengine_voice_zh_male_default",
    "zh_warm_female": "volcengine_voice_zh_warm_female",
    "zh_steady_male": "volcengine_voice_zh_steady_male",
    "zh_energetic_female": "volcengine_voice_zh_energetic_female",
    "zh_knowledge_host": "volcengine_voice_zh_knowledge_host",
    "zh_business_narration": "volcengine_voice_zh_business_narration",
    "zh_casual_spoken": "volcengine_voice_zh_casual_spoken",
}


@dataclass(frozen=True)
class ResolvedVoice:
    requested_key: str
    resolved_key: str
    provider_voice_id: str
    used_fallback: bool


@dataclass(frozen=True)
class NormalizedVoiceRequest:
    requested_key: str | None
    legacy_provider_voice_id: str | None = None


def normalize_tts_language(language: str | None) -> str:
    normalized = (language or DEFAULT_TTS_LANGUAGE).strip() or DEFAULT_TTS_LANGUAGE
    if normalized != DEFAULT_TTS_LANGUAGE:
        raise HTTPException(status_code=422, detail="当前仅支持中文配音，请选择中文音色。")
    return normalized


def _configured_voice_id(key: str) -> str:
    return str(getattr(settings, VOICE_SETTING_MAP[key], "") or "").strip()


def _default_voice_key() -> str:
    configured = (settings.volcengine_default_voice_key or DEFAULT_VOICE_KEY).strip()
    if configured not in VOICE_LANGUAGE_MAP:
        logger.error("Invalid default TTS voice key configured default_voice_key=%s", configured)
        return DEFAULT_VOICE_KEY
    return configured


def normalize_legacy_voice_request(voice: str | None, voice_type: str | None) -> NormalizedVoiceRequest:
    public_voice = (voice or "").strip()
    legacy_voice = (voice_type or "").strip()

    if public_voice:
        if public_voice not in VOICE_LANGUAGE_MAP:
            raise HTTPException(status_code=422, detail="不支持所选音色，请重新选择。")
        return NormalizedVoiceRequest(public_voice)

    if legacy_voice in VOICE_LANGUAGE_MAP:
        return NormalizedVoiceRequest(legacy_voice)
    if legacy_voice in LEGACY_PROVIDER_VOICE_COMPATIBILITY:
        logger.warning("Deprecated TTS voice_type compatibility used legacy_voice_slot=%s", 1 if legacy_voice == "BV001_streaming" else 2)
        return NormalizedVoiceRequest(DEFAULT_VOICE_KEY, LEGACY_PROVIDER_VOICE_COMPATIBILITY[legacy_voice])
    return NormalizedVoiceRequest(legacy_voice or None)


def resolve_voice(
    requested_voice_key: str | None,
    language: str | None,
    *,
    legacy_provider_voice_id: str | None = None,
) -> ResolvedVoice:
    normalized_language = normalize_tts_language(language)
    default_key = _default_voice_key()
    requested_key = (requested_voice_key or default_key).strip()

    if requested_key not in VOICE_LANGUAGE_MAP:
        raise HTTPException(status_code=422, detail="不支持所选音色，请重新选择。")
    if VOICE_LANGUAGE_MAP[requested_key] != normalized_language:
        raise HTTPException(status_code=422, detail="所选音色与配音语言不匹配，请重新选择。")

    if legacy_provider_voice_id is not None:
        if legacy_provider_voice_id not in LEGACY_PROVIDER_VOICE_COMPATIBILITY.values():
            raise HTTPException(status_code=422, detail="不支持所选音色，请重新选择。")
        return ResolvedVoice(requested_key, DEFAULT_VOICE_KEY, legacy_provider_voice_id, True)

    provider_voice_id = _configured_voice_id(requested_key)
    resolved_key = requested_key
    fallback_reason = ""

    if not provider_voice_id:
        resolved_key = default_key
        provider_voice_id = _configured_voice_id(default_key)
        fallback_reason = "voice_not_configured"

    if not provider_voice_id:
        provider_voice_id = (settings.volcengine_tts_voice_type or "").strip()
        fallback_reason = "legacy_default"

    if not provider_voice_id:
        raise HTTPException(status_code=503, detail="配音服务暂未配置，请稍后重试。")

    used_fallback = requested_key != resolved_key or bool(fallback_reason)
    if used_fallback:
        logger.warning(
            "TTS voice fallback requested_voice_key=%s resolved_voice_key=%s fallback_reason=%s",
            requested_key,
            resolved_key,
            fallback_reason,
        )

    return ResolvedVoice(requested_key, resolved_key, provider_voice_id, used_fallback)
