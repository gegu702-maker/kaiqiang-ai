from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
import json
import logging
import math
from pathlib import Path
import re
import time

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
    segment_text = str(getattr(segment, "text", "")).strip()
    compact_segment_text = "".join(segment_text.split())
    compact_word_text = "".join(str(getattr(word, "word", "")) for word in words).strip()
    # Faster-Whisper may expose only a sparse subset of word timestamps for a
    # complete segment. Never replace the segment's recognized text with that
    # sparse subset: it creates a deceptively full time range with a truncated
    # transcript. Fall back to bounded sentence splitting in that case.
    word_timestamps_complete = bool(compact_segment_text) and compact_word_text == compact_segment_text
    if words and word_timestamps_complete:
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
        # segment.text is the canonical transcript. Word timestamps may define
        # boundaries only when they reproduce it exactly; otherwise retain the
        # complete segment text and split its time interval proportionally.
        if "".join(chunk.text for chunk in chunks) == segment_text:
            return chunks

    text = segment_text
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
    last_timestamp_seconds: float = 0.0
    raw_segment_count: int = 0
    raw_transcript_chars: int = 0
    word_timestamp_chars: int = 0
    word_timestamp_count: int = 0
    first_timestamp_seconds: float = 0.0
    normalized_text_chars: int = 0
    replacement_char_count: int = 0
    control_char_count: int = 0


def _normalize_transcription(
    segments,
    *,
    pass_label: str = "",
) -> tuple[list[ASRSegment], str, float, int, int, int, int, float, int, int, int]:
    raw_segments = list(segments)
    if pass_label:
        request_id = current_request_id()
        for index, segment in enumerate(raw_segments):
            text = str(getattr(segment, "text", "")).strip()
            logger.warning(
                "viral_asr_segment request_id=%s pass=%s index=%s start=%.3f end=%.3f text_chars=%s "
                "cjk_chars=%s no_speech_prob=%s avg_logprob=%s compression_ratio=%s",
                request_id,
                pass_label,
                index,
                float(segment.start),
                float(segment.end),
                len(text),
                sum(1 for char in text if "\u4e00" <= char <= "\u9fff"),
                getattr(segment, "no_speech_prob", None),
                getattr(segment, "avg_logprob", None),
                getattr(segment, "compression_ratio", None),
            )
    raw_transcript_chars = sum(len(str(getattr(segment, "text", "")).strip()) for segment in raw_segments)
    word_timestamp_count = sum(len(getattr(segment, "words", None) or []) for segment in raw_segments)
    word_timestamp_chars = sum(
        len("".join(str(getattr(word, "word", "")) for word in (getattr(segment, "words", None) or [])))
        for segment in raw_segments
    )
    normalized = _merge_short_adjacent_context(
        [chunk for segment in raw_segments for chunk in _split_transcription_segment(segment)]
    )
    transcript = "\n".join(segment.text for segment in normalized).strip()
    normalized_text_chars = sum(len(segment.text) for segment in normalized)
    replacement_char_count = transcript.count("\ufffd")
    control_char_count = sum(1 for char in transcript if ord(char) < 32 and char not in "\n\r\t")
    first_timestamp = min((segment.start for segment in normalized), default=0.0)
    coverage = max((segment.end for segment in normalized), default=0.0)
    return (
        normalized,
        transcript,
        coverage,
        len(raw_segments),
        raw_transcript_chars,
        word_timestamp_chars,
        word_timestamp_count,
        first_timestamp,
        normalized_text_chars,
        replacement_char_count,
        control_char_count,
    )


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
        initial_started = time.perf_counter()
        segments, _info = model.transcribe(str(audio_path), **transcribe_options)
        (
            normalized_segments,
            transcript,
            coverage_seconds,
            raw_segment_count,
            raw_transcript_chars,
            word_timestamp_chars,
            word_timestamp_count,
            first_timestamp_seconds,
            normalized_text_chars,
            replacement_char_count,
            control_char_count,
        ) = _normalize_transcription(segments, pass_label="initial")
        initial_elapsed = time.perf_counter() - initial_started
        logger.warning(
            "viral_asr request_id=%s stage=transcribe outcome=pass_completed pass=initial "
            "raw_segment_count=%s raw_transcript_chars=%s word_timestamp_count=%s word_timestamp_chars=%s "
            "normalized_text_chars=%s transcript_chars=%s first_timestamp_seconds=%.3f last_timestamp_seconds=%.3f "
            "replacement_char_count=%s control_char_count=%s elapsed_seconds=%.3f",
            request_id,
            raw_segment_count,
            raw_transcript_chars,
            word_timestamp_count,
            word_timestamp_chars,
            normalized_text_chars,
            len(transcript),
            first_timestamp_seconds,
            coverage_seconds,
            replacement_char_count,
            control_char_count,
            initial_elapsed,
        )
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
            recovery_options = {**transcribe_options, "vad_filter": False, "word_timestamps": False}
            recovery_started = time.perf_counter()
            recovery_segments, _recovery_info = model.transcribe(str(audio_path), **recovery_options)
            (
                recovered_normalized,
                recovered_transcript,
                recovered_coverage,
                recovered_raw_segment_count,
                recovered_raw_transcript_chars,
                recovered_word_timestamp_chars,
                recovered_word_timestamp_count,
                recovered_first_timestamp_seconds,
                recovered_normalized_text_chars,
                recovered_replacement_char_count,
                recovered_control_char_count,
            ) = _normalize_transcription(recovery_segments, pass_label="recovery")
            recovery_elapsed = time.perf_counter() - recovery_started
            if len(recovered_transcript) > len(transcript) or recovered_coverage > coverage_seconds:
                normalized_segments = recovered_normalized
                transcript = recovered_transcript
                coverage_seconds = recovered_coverage
                raw_segment_count = recovered_raw_segment_count
                raw_transcript_chars = recovered_raw_transcript_chars
                word_timestamp_chars = recovered_word_timestamp_chars
                word_timestamp_count = recovered_word_timestamp_count
                first_timestamp_seconds = recovered_first_timestamp_seconds
                normalized_text_chars = recovered_normalized_text_chars
                replacement_char_count = recovered_replacement_char_count
                control_char_count = recovered_control_char_count
                recovery_used = True
            logger.warning(
                "viral_asr request_id=%s stage=transcribe outcome=recovery_completed recovery_used=%s "
                "recovered_coverage_seconds=%.3f recovered_transcript_chars=%s recovered_raw_segment_count=%s "
                "recovered_raw_transcript_chars=%s recovered_word_timestamp_count=%s recovered_word_timestamp_chars=%s "
                "recovered_normalized_text_chars=%s recovered_first_timestamp_seconds=%.3f "
                "recovered_replacement_char_count=%s recovered_control_char_count=%s elapsed_seconds=%.3f "
                "vad_filter=False word_timestamps=False initial_prompt=%s hotwords=%s",
                request_id,
                recovery_used,
                recovered_coverage,
                len(recovered_transcript),
                recovered_raw_segment_count,
                recovered_raw_transcript_chars,
                recovered_word_timestamp_count,
                recovered_word_timestamp_chars,
                recovered_normalized_text_chars,
                recovered_first_timestamp_seconds,
                recovered_replacement_char_count,
                recovered_control_char_count,
                recovery_elapsed,
                "initial_prompt" in recovery_options,
                "hotwords" in recovery_options,
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
        "segment_count=%s transcript_chars=%s raw_segment_count=%s raw_transcript_chars=%s "
        "word_timestamp_count=%s word_timestamp_chars=%s normalized_text_chars=%s "
        "first_timestamp_seconds=%.3f last_timestamp_seconds=%.3f replacement_char_count=%s "
        "control_char_count=%s recovery_attempted=%s recovery_used=%s",
        request_id,
        coverage_seconds,
        len(normalized_segments),
        len(transcript),
        raw_segment_count,
        raw_transcript_chars,
        word_timestamp_count,
        word_timestamp_chars,
        normalized_text_chars,
        first_timestamp_seconds,
        coverage_seconds,
        replacement_char_count,
        control_char_count,
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
        last_timestamp_seconds=coverage_seconds,
        raw_segment_count=raw_segment_count,
        raw_transcript_chars=raw_transcript_chars,
        word_timestamp_chars=word_timestamp_chars,
        word_timestamp_count=word_timestamp_count,
        first_timestamp_seconds=first_timestamp_seconds,
        normalized_text_chars=normalized_text_chars,
        replacement_char_count=replacement_char_count,
        control_char_count=control_char_count,
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


def _mean_segment_metric(segments, name: str) -> float | None:
    values = [
        float(value)
        for segment in segments
        if (value := getattr(segment, name, None)) is not None
    ]
    return round(sum(values) / len(values), 6) if values else None


def _duplicate_segment_ratio(texts: list[str]) -> float:
    total = sum(len(text) for text in texts)
    if not total:
        return 0.0
    seen: set[str] = set()
    duplicate_chars = 0
    for text in texts:
        compact = "".join(text.split())
        if compact in seen:
            duplicate_chars += len(text)
        else:
            seen.add(compact)
    return round(duplicate_chars / total, 6)


def _redact_asr_preview(text: str, limit: int = 60) -> str:
    value = re.sub(r"https?://\S+", "[URL]", text)
    value = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", value)
    value = re.sub(r"\d", "#", value)
    return value[:limit]


def _run_asr_diagnostic_matrix(audio_path: Path, language: str, expected_duration: float) -> list[dict]:
    request_id = current_request_id()
    model = _get_model()
    base = {
        "language": language if language in {"zh", "en"} else "zh",
        "beam_size": settings.faster_whisper_beam_size,
        "condition_on_previous_text": True,
        "word_timestamps": False,
    }
    configurations = [
        ("A", {**base, "vad_filter": False}),
        ("B", {**base, "vad_filter": True}),
        ("C", {**base, "vad_filter": False, "initial_prompt": FINANCIAL_INITIAL_PROMPT}),
        ("D", {**base, "vad_filter": False, "hotwords": FINANCIAL_HOTWORDS}),
    ]
    results: list[dict] = []
    for label, options in configurations:
        started = time.perf_counter()
        segment_generator, _info = model.transcribe(str(audio_path), **options)
        segments = list(segment_generator)
        elapsed = time.perf_counter() - started
        texts = [str(getattr(segment, "text", "")).strip() for segment in segments]
        transcript = "".join(texts)
        cjk_chars = sum(1 for char in transcript if "\u4e00" <= char <= "\u9fff")
        first_timestamp = min((float(segment.start) for segment in segments), default=0.0)
        last_timestamp = max((float(segment.end) for segment in segments), default=0.0)
        coverage_ratio = last_timestamp / expected_duration if expected_duration else 0.0
        summary = {
            "config": label,
            "elapsed_seconds": round(elapsed, 3),
            "segment_count": len(segments),
            "text_chars": len(transcript),
            "cjk_chars": cjk_chars,
            "first_timestamp_seconds": round(first_timestamp, 3),
            "last_timestamp_seconds": round(last_timestamp, 3),
            "coverage_ratio": round(coverage_ratio, 6),
            "cjk_chars_per_second": round(cjk_chars / max(last_timestamp, 1), 6),
            "duplicate_segment_ratio": _duplicate_segment_ratio(texts),
            "avg_no_speech_prob": _mean_segment_metric(segments, "no_speech_prob"),
            "avg_logprob": _mean_segment_metric(segments, "avg_logprob"),
            "avg_compression_ratio": _mean_segment_metric(segments, "compression_ratio"),
            "vad_filter": options["vad_filter"],
            "word_timestamps": options["word_timestamps"],
            "initial_prompt": "initial_prompt" in options,
            "hotwords": "hotwords" in options,
            "preview_first": [_redact_asr_preview(text) for text in texts[:3]],
            "preview_last": [_redact_asr_preview(text) for text in texts[-3:]],
        }
        logger.warning(
            "viral_asr_matrix request_id=%s stage=diagnostic config=%s outcome=completed metrics=%s",
            request_id,
            label,
            json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        )
        for index, segment in enumerate(segments):
            text = texts[index]
            logger.warning(
                "viral_asr_matrix_segment request_id=%s config=%s index=%s start=%.3f end=%.3f "
                "text_chars=%s cjk_chars=%s no_speech_prob=%s avg_logprob=%s compression_ratio=%s",
                request_id,
                label,
                index,
                float(segment.start),
                float(segment.end),
                len(text),
                sum(1 for char in text if "\u4e00" <= char <= "\u9fff"),
                getattr(segment, "no_speech_prob", None),
                getattr(segment, "avg_logprob", None),
                getattr(segment, "compression_ratio", None),
            )
        results.append(summary)
    return results


async def run_asr_diagnostic_matrix(audio_path: Path, language: str, expected_duration: float) -> list[dict]:
    return await asyncio.to_thread(_run_asr_diagnostic_matrix, audio_path, language, expected_duration)
