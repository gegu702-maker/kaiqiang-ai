from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
import logging
import math
from pathlib import Path

from app.core.config import settings
from app.services.financial_terms import FINANCIAL_HOTWORDS, FINANCIAL_INITIAL_PROMPT
from app.services.viral_diagnostics import current_request_id


logger = logging.getLogger(__name__)


def _join_segment_text(left: str, right: str) -> str:
    if not left:
        return right.strip()
    if not right:
        return left.strip()
    if any("\u4e00" <= char <= "\u9fff" for char in f"{left}{right}"):
        return f"{left.rstrip()}{right.lstrip()}"
    return f"{left.rstrip()} {right.lstrip()}"


def _split_text_interval(text: str, start: float, end: float, max_seconds: float) -> list[ASRSegment]:
    text = text.strip()
    duration = max(0.0, end - start)
    if not text:
        return []
    chunk_count = max(1, math.ceil(duration / max_seconds))
    chunks: list[ASRSegment] = []
    cursor = 0
    for index in range(chunk_count):
        ideal_end = round(len(text) * (index + 1) / chunk_count)
        if index + 1 < chunk_count:
            max_text_end = max(cursor + 1, len(text) - (chunk_count - index - 1))
            candidates = [
                position + 1
                for position in range(cursor, min(max_text_end, ideal_end + 8))
                if text[position] in "。！？!?；;，,"
            ]
            text_end = min(candidates, key=lambda position: abs(position - ideal_end)) if candidates else min(ideal_end, max_text_end)
        else:
            text_end = len(text)
        chunk_text = text[cursor:text_end].strip()
        chunk_start = start + duration * index / chunk_count
        chunk_end = min(end, start + duration * (index + 1) / chunk_count)
        if chunk_text:
            chunks.append(ASRSegment(start=chunk_start, end=chunk_end, text=chunk_text))
        cursor = text_end
    return chunks


def _split_transcription_segment(segment, max_seconds: float = 8.0) -> list[ASRSegment]:
    words = [word for word in (getattr(segment, "words", None) or []) if str(getattr(word, "word", "")).strip()]
    if words:
        chunks: list[ASRSegment] = []
        chunk_words = []
        for word in words:
            word_start = float(word.start)
            word_end = float(word.end)
            if word_end - word_start > max_seconds:
                if chunk_words:
                    chunks.append(
                        ASRSegment(
                            start=float(chunk_words[0].start),
                            end=float(chunk_words[-1].end),
                            text="".join(str(item.word) for item in chunk_words).strip(),
                        )
                    )
                    chunk_words = []
                chunks.extend(_split_text_interval(str(word.word), word_start, word_end, max_seconds))
                continue
            if chunk_words and word_end - float(chunk_words[0].start) > max_seconds:
                chunks.append(
                    ASRSegment(
                        start=float(chunk_words[0].start),
                        end=float(chunk_words[-1].end),
                        text="".join(str(item.word) for item in chunk_words).strip(),
                    )
                )
                chunk_words = []
            chunk_words.append(word)
            text = "".join(str(item.word) for item in chunk_words).strip()
            if text.endswith(("。", "！", "？", "!", "?", "；", ";")):
                chunks.append(ASRSegment(start=float(chunk_words[0].start), end=float(chunk_words[-1].end), text=text))
                chunk_words = []
        if chunk_words:
            chunks.append(
                ASRSegment(
                    start=float(chunk_words[0].start),
                    end=float(chunk_words[-1].end),
                    text="".join(str(item.word) for item in chunk_words).strip(),
                )
            )
        return chunks

    text = str(segment.text).strip()
    if not text:
        return []
    start = float(segment.start)
    end = float(segment.end)
    return _split_text_interval(text, start, end, max_seconds)


def _merge_short_adjacent_context(segments: list[ASRSegment], max_seconds: float = 8.0) -> list[ASRSegment]:
    merged: list[ASRSegment] = []
    index = 0
    while index < len(segments):
        current = segments[index]
        compact = "".join(current.text.split())
        is_boundary_fragment = (
            (current.end - current.start <= 0.75 or len(compact) <= 4)
            and not current.text.rstrip().endswith(("。", "！", "？", "!", "?", "；", ";"))
        )
        if is_boundary_fragment and index + 1 < len(segments):
            following = segments[index + 1]
            gap = max(0.0, following.start - current.end)
            if gap <= 0.5 and following.end - current.start <= max_seconds:
                merged.append(
                    ASRSegment(
                        start=current.start,
                        end=following.end,
                        text=_join_segment_text(current.text, following.text),
                    )
                )
                index += 2
                continue
        if is_boundary_fragment and merged:
            previous = merged[-1]
            gap = max(0.0, current.start - previous.end)
            if gap <= 0.5 and current.end - previous.start <= max_seconds:
                merged[-1] = ASRSegment(
                    start=previous.start,
                    end=current.end,
                    text=_join_segment_text(previous.text, current.text),
                )
                index += 1
                continue
        merged.append(current)
        index += 1
    return merged


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
    recovery_attempted: bool = False
    recovery_used: bool = False


def _normalize_transcription(segments) -> tuple[list[ASRSegment], str, float]:
    normalized = _merge_short_adjacent_context(
        [chunk for segment in segments for chunk in _split_transcription_segment(segment)]
    )
    transcript = "\n".join(segment.text for segment in normalized).strip()
    coverage = max((segment.end for segment in normalized), default=0.0)
    return normalized, transcript, coverage


def _needs_vad_recovery(*, transcript: str, coverage_seconds: float, expected_duration: float, language: str) -> bool:
    compact_chars = len("".join(transcript.split()))
    if expected_duration >= 30 and coverage_seconds < expected_duration * 0.8:
        return True
    if language == "zh" and coverage_seconds >= 60 and compact_chars / max(coverage_seconds, 1) < 1.5:
        return True
    return False


def _transcribe_with_faster_whisper(audio_path: Path, language: str, expected_duration: float = 0.0) -> ASRResult:
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

    domain = settings.viral_asr_domain.strip().lower()
    logger.warning(
        "viral_asr request_id=%s stage=transcribe outcome=started model=%s device=%s compute_type=%s language=%s beam_size=%s vad_filter=%s word_timestamps=%s domain=%s initial_prompt=%s hotwords=%s",
        request_id,
        settings.faster_whisper_model_size,
        settings.faster_whisper_device,
        settings.faster_whisper_compute_type,
        language if language in {"zh", "en"} else "zh",
        settings.faster_whisper_beam_size,
        settings.faster_whisper_vad_filter,
        settings.faster_whisper_word_timestamps,
        domain or "general",
        domain == "financial" and settings.viral_asr_use_initial_prompt,
        domain == "financial" and settings.viral_asr_use_hotwords,
    )
    try:
        transcribe_options = {
            "language": language if language in {"zh", "en"} else "zh",
            "vad_filter": settings.faster_whisper_vad_filter,
            "beam_size": settings.faster_whisper_beam_size,
            "condition_on_previous_text": True,
            "word_timestamps": settings.faster_whisper_word_timestamps,
        }
        if domain == "financial" and settings.viral_asr_use_initial_prompt:
            transcribe_options["initial_prompt"] = FINANCIAL_INITIAL_PROMPT
        if domain == "financial" and settings.viral_asr_use_hotwords:
            transcribe_options["hotwords"] = FINANCIAL_HOTWORDS
        segments, _info = model.transcribe(str(audio_path), **transcribe_options)
        normalized_segments, transcript, coverage_seconds = _normalize_transcription(segments)
        recovery_attempted = _needs_vad_recovery(
            transcript=transcript,
            coverage_seconds=coverage_seconds,
            expected_duration=expected_duration,
            language=transcribe_options["language"],
        )
        recovery_used = False
        if recovery_attempted and transcribe_options["vad_filter"]:
            logger.warning(
                "viral_asr request_id=%s stage=transcribe outcome=recovery_started reason=low_completeness "
                "initial_coverage_seconds=%.3f initial_transcript_chars=%s expected_duration_seconds=%.3f",
                request_id,
                coverage_seconds,
                len(transcript),
                expected_duration,
            )
            recovery_options = {**transcribe_options, "vad_filter": False}
            recovery_segments, _recovery_info = model.transcribe(str(audio_path), **recovery_options)
            recovered_normalized, recovered_transcript, recovered_coverage = _normalize_transcription(recovery_segments)
            if len(recovered_transcript) > len(transcript) or recovered_coverage > coverage_seconds:
                normalized_segments = recovered_normalized
                transcript = recovered_transcript
                coverage_seconds = recovered_coverage
                recovery_used = True
            logger.warning(
                "viral_asr request_id=%s stage=transcribe outcome=recovery_completed recovery_used=%s "
                "recovered_coverage_seconds=%.3f recovered_transcript_chars=%s",
                request_id,
                recovery_used,
                recovered_coverage,
                len(recovered_transcript),
            )
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
    logger.warning(
        "viral_asr request_id=%s stage=transcribe outcome=completed coverage_seconds=%.3f "
        "segment_count=%s transcript_chars=%s recovery_attempted=%s recovery_used=%s",
        request_id,
        coverage_seconds,
        len(normalized_segments),
        len(transcript),
        recovery_attempted,
        recovery_used,
    )
    return ASRResult(
        ok=True,
        transcript=transcript,
        segments=normalized_segments,
        coverage_seconds=coverage_seconds,
        recovery_attempted=recovery_attempted,
        recovery_used=recovery_used,
    )


@lru_cache(maxsize=1)
def _get_model():
    from faster_whisper import WhisperModel

    return WhisperModel(
        settings.faster_whisper_model_size,
        device=settings.faster_whisper_device,
        compute_type=settings.faster_whisper_compute_type,
    )


async def transcribe_audio(audio_path: Path, language: str = "zh", expected_duration: float = 0.0) -> ASRResult:
    return await asyncio.to_thread(_transcribe_with_faster_whisper, audio_path, language, expected_duration)
