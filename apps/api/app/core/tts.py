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
}


def get_tts_voice(language: str) -> TTSVoiceConfig:
    return MINIMAX_TTS_VOICES[language]
