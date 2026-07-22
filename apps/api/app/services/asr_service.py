from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
import logging
from pathlib import Path

from app.core.config import settings
from app.services.viral_diagnostics import current_request_id


logger = logging.getLogger(__name__)


@dataclass
class ASRSegment:
    start: float
    end: float
    text: str


@dataclass
class ASRResult:
    ok: bool
    transcript: str = ""
    fallback_reason: str = ""
    segments: list[ASRSegment] | None = None
    coverage_seconds: float = 0.0
    provider: str = "faster-whisper"
    error_code: str = ""
    retryable: bool = False
    diagnostic: str = ""


def _transcribe_with_faster_whisper(audio_path: Path, language: str) -> ASRResult:
    request_id = current_request_id()
    logger.info(
        "viral_asr request_id=%s stage=model_load provider=faster-whisper model=%s device=%s compute_type=%s audio_bytes=%s",
        request_id,
        settings.faster_whisper_model_size,
        settings.faster_whisper_device,
        settings.faster_whisper_compute_type,
        audio_path.stat().st_size if audio_path.exists() else -1,
    )
    try:
        model = _get_model()
    except ImportError as error:
        diagnostic = f"{type(error).__name__}: {error}"[:500]
        logger.exception("viral_asr request_id=%s stage=model_load outcome=dependency_missing", request_id)
        return ASRResult(
            ok=False,
            fallback_reason="ASR 模型依赖不可用。",
            error_code="asr_dependency_missing",
            retryable=False,
            diagnostic=diagnostic,
        )
    except Exception as error:
        diagnostic = f"{type(error).__name__}: {error}"[:500]
        logger.exception("viral_asr request_id=%s stage=model_load outcome=model_unavailable", request_id)
        return ASRResult(
            ok=False,
            fallback_reason="ASR 模型加载或下载失败。",
            error_code="asr_model_unavailable",
            retryable=True,
            diagnostic=diagnostic,
        )

    logger.info("viral_asr request_id=%s stage=transcribe outcome=started", request_id)
    try:
        segments, _info = model.transcribe(
            str(audio_path),
            language=language if language in {"zh", "en"} else "zh",
            vad_filter=True,
            beam_size=5,
        )
        normalized_segments = [
            ASRSegment(start=float(segment.start), end=float(segment.end), text=segment.text.strip())
            for segment in segments
            if segment.text.strip()
        ]
        transcript = "\n".join(segment.text for segment in normalized_segments).strip()
    except Exception as error:
        diagnostic = f"{type(error).__name__}: {error}"[:500]
        logger.exception("viral_asr request_id=%s stage=transcribe outcome=failed", request_id)
        return ASRResult(
            ok=False,
            fallback_reason="ASR 推理失败。",
            error_code="asr_transcription_failed",
            retryable=True,
            diagnostic=diagnostic,
        )

    if not transcript:
        logger.warning("viral_asr request_id=%s stage=transcribe outcome=empty", request_id)
        return ASRResult(
            ok=False,
            fallback_reason="未识别到可用语音内容。",
            error_code="asr_empty_transcript",
            retryable=False,
        )
    coverage_seconds = max((segment.end for segment in normalized_segments), default=0.0)
    logger.info(
        "viral_asr request_id=%s stage=transcribe outcome=completed coverage_seconds=%.3f segment_count=%s transcript_chars=%s",
        request_id,
        coverage_seconds,
        len(normalized_segments),
        len(transcript),
    )
    return ASRResult(ok=True, transcript=transcript, segments=normalized_segments, coverage_seconds=coverage_seconds)


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
