from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import settings


@dataclass
class ASRResult:
    ok: bool
    transcript: str = ""
    fallback_reason: str = ""


def _transcribe_with_faster_whisper(audio_path: Path, language: str) -> ASRResult:
    try:
        model = _get_model()
    except ImportError:
        return ASRResult(ok=False, fallback_reason="服务端未安装 Faster-Whisper，暂时无法自动转写，请上传视频或粘贴文案继续分析。")

    try:
        segments, _info = model.transcribe(
            str(audio_path),
            language=language if language in {"zh", "en", "ja", "ko", "es", "fr", "ru"} else "zh",
            vad_filter=True,
            beam_size=5,
        )
        transcript = "".join(segment.text.strip() for segment in segments).strip()
    except Exception:
        return ASRResult(ok=False, fallback_reason="该视频暂不支持自动转写，请上传视频继续分析。")

    if not transcript:
        return ASRResult(ok=False, fallback_reason="未识别到可用语音内容，请上传更清晰的视频或粘贴文案继续分析。")
    return ASRResult(ok=True, transcript=transcript)


@lru_cache(maxsize=1)
def _get_model():
    from faster_whisper import WhisperModel

    return WhisperModel(
        settings.faster_whisper_model_size,
        device=settings.faster_whisper_device,
        compute_type=settings.faster_whisper_compute_type,
    )


async def transcribe_audio(audio_path: Path, language: str = "zh") -> ASRResult:
    return await asyncio.to_thread(_transcribe_with_faster_whisper, audio_path, language)
