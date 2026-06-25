from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class VoiceConfig:
    id: str
    label: str
    gender: str
    provider: str
    language: str
    enabled: bool = True


@dataclass(frozen=True)
class LanguageConfig:
    code: str
    label: str
    native_label: str
    enabled: bool
    coming_soon: bool
    voices: tuple[VoiceConfig, ...]


DEFAULT_TTS_LANGUAGE = "zh-CN"
DEFAULT_TTS_VOICE = "BV001_streaming"
LANGUAGE_ALIASES = {
    "zh": "zh-CN",
    "zh_cn": "zh-CN",
    "zh-cn": "zh-CN",
    "en": "en-US",
    "en_us": "en-US",
    "en-us": "en-US",
    "ja": "ja-JP",
    "ja_jp": "ja-JP",
    "ja-jp": "ja-JP",
    "ko": "ko-KR",
    "ko_kr": "ko-KR",
    "ko-kr": "ko-KR",
}


def normalize_tts_language(language: str | None) -> str:
    raw = (language or DEFAULT_TTS_LANGUAGE).strip() or DEFAULT_TTS_LANGUAGE
    return LANGUAGE_ALIASES.get(raw.lower(), raw)


def _voice_label(voice_id: str) -> str:
    labels = {
        "BV001_streaming": "Mandarin female",
        "BV002_streaming": "Mandarin male",
    }
    return labels.get(voice_id, voice_id)


def _voices_for(language: str, pairs: tuple[tuple[str, str], ...]) -> tuple[VoiceConfig, ...]:
    voices: list[VoiceConfig] = []
    for gender, voice_id in pairs:
        clean_voice_id = voice_id.strip()
        if clean_voice_id:
            voices.append(
                VoiceConfig(
                    id=clean_voice_id,
                    label=_voice_label(clean_voice_id),
                    gender=gender,
                    provider="volcengine",
                    language=language,
                )
            )
    return tuple(voices)


def _build_voice_registry() -> tuple[LanguageConfig, ...]:
    zh_voices = _voices_for(
        "zh-CN",
        (
            ("female", settings.volcengine_tts_zh_cn_female_voice_type or settings.volcengine_tts_voice_type or DEFAULT_TTS_VOICE),
            ("male", settings.volcengine_tts_zh_cn_male_voice_type),
        ),
    )
    en_voices = _voices_for(
        "en-US",
        (
            ("female", settings.volcengine_tts_en_us_female_voice_type),
            ("male", settings.volcengine_tts_en_us_male_voice_type),
        ),
    )
    ja_voices = _voices_for(
        "ja-JP",
        (
            ("female", settings.volcengine_tts_ja_jp_female_voice_type),
            ("male", settings.volcengine_tts_ja_jp_male_voice_type),
        ),
    )
    ko_voices = _voices_for(
        "ko-KR",
        (
            ("female", settings.volcengine_tts_ko_kr_female_voice_type),
            ("male", settings.volcengine_tts_ko_kr_male_voice_type),
        ),
    )
    return (
        LanguageConfig("zh-CN", "Chinese Mandarin", "中文普通话", bool(zh_voices), not bool(zh_voices), zh_voices),
        LanguageConfig("en-US", "English", "English", bool(en_voices), not bool(en_voices), en_voices),
        LanguageConfig("ja-JP", "Japanese", "日本語", bool(ja_voices), not bool(ja_voices), ja_voices),
        LanguageConfig("ko-KR", "Korean", "한국어", bool(ko_voices), not bool(ko_voices), ko_voices),
    )


def get_voice_registry() -> tuple[LanguageConfig, ...]:
    return _build_voice_registry()


def serialize_voice_registry() -> list[dict]:
    return [
        {
            "code": language.code,
            "label": language.label,
            "nativeLabel": language.native_label,
            "enabled": language.enabled,
            "comingSoon": language.coming_soon,
            "voices": [
                {
                    "id": voice.id,
                    "label": voice.label,
                    "gender": voice.gender,
                    "provider": voice.provider,
                    "language": voice.language,
                    "enabled": voice.enabled,
                }
                for voice in language.voices
            ],
        }
        for language in get_voice_registry()
    ]


def get_language_config(language: str | None) -> LanguageConfig:
    selected = normalize_tts_language(language)
    for config in get_voice_registry():
        if config.code == selected:
            return config
    supported = ", ".join(config.code for config in get_voice_registry())
    raise HTTPException(status_code=400, detail=f"Unsupported TTS language '{selected}'. Supported languages: {supported}.")


def validate_tts_voice(language: str | None, voice_id: str | None) -> VoiceConfig:
    config = get_language_config(language)
    if not config.enabled:
        raise HTTPException(status_code=400, detail=f"TTS language '{config.code}' is coming soon and is not enabled yet.")
    voices = tuple(voice for voice in config.voices if voice.enabled)
    if not voices:
        raise HTTPException(status_code=400, detail=f"TTS language '{config.code}' has no enabled voices.")
    selected_voice_id = (voice_id or voices[0].id).strip()
    for voice in voices:
        if voice.id == selected_voice_id:
            return voice
    allowed = ", ".join(voice.id for voice in voices)
    raise HTTPException(status_code=400, detail=f"Unsupported TTS voice '{selected_voice_id}' for language '{config.code}'. Available voices: {allowed}.")
