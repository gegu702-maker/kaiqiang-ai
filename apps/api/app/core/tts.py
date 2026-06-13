from dataclasses import dataclass


@dataclass(frozen=True)
class TTSVoiceConfig:
    language: str
    voice_name: str
    display_name: str


MINIMAX_TTS_VOICES: dict[str, TTSVoiceConfig] = {
    "zh": TTSVoiceConfig(
        language="zh",
        voice_name="minimax_zh_female",
        display_name="MiniMax 中文女声",
    ),
    "en": TTSVoiceConfig(
        language="en",
        voice_name="minimax_en_female",
        display_name="MiniMax English Female",
    ),
    # TODO: Replace fallback voice_name values with provider-confirmed multilingual voices.
    "ja": TTSVoiceConfig(
        language="ja",
        voice_name="minimax_en_female",
        display_name="MiniMax Japanese fallback",
    ),
    "ko": TTSVoiceConfig(
        language="ko",
        voice_name="minimax_en_female",
        display_name="MiniMax Korean fallback",
    ),
    "es": TTSVoiceConfig(
        language="es",
        voice_name="minimax_en_female",
        display_name="MiniMax Spanish fallback",
    ),
    "fr": TTSVoiceConfig(
        language="fr",
        voice_name="minimax_en_female",
        display_name="MiniMax French fallback",
    ),
    "ru": TTSVoiceConfig(
        language="ru",
        voice_name="minimax_en_female",
        display_name="MiniMax Russian fallback",
    ),
}


def get_tts_voice(language: str) -> TTSVoiceConfig:
    return MINIMAX_TTS_VOICES.get(language, MINIMAX_TTS_VOICES["en"])
