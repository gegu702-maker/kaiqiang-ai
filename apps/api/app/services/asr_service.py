from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
import logging
import math
import multiprocessing
import os
from pathlib import Path
import queue
import threading
import time
from typing import Any, Callable

from app.core.config import settings
from app.services.financial_terms import FINANCIAL_HOTWORDS, FINANCIAL_INITIAL_PROMPT
from app.services.viral_deadline import current_pipeline_deadline
from app.services.viral_diagnostics import bind_request_id, current_request_id, reset_request_id


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


def _transcribe_with_faster_whisper(
    audio_path: Path,
    language: str,
    expected_duration: float = 0.0,
    model_ready_callback: Callable[[dict[str, Any]], None] | None = None,
) -> ASRResult:
    request_id = current_request_id()
    logger.info(
        "viral_asr request_id=%s stage=model_load provider=faster-whisper model=%s device=%s compute_type=%s audio_bytes=%s",
        request_id,
        settings.faster_whisper_model_size,
        settings.faster_whisper_device,
        settings.faster_whisper_compute_type,
        audio_path.stat().st_size if audio_path.exists() else -1,
    )
    model_load_started = time.perf_counter()
    cache_info = getattr(_get_model, "cache_info", None)
    cache_info_before = cache_info() if callable(cache_info) else None
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

    cache_info_after = cache_info() if callable(cache_info) else None
    model_initialization_elapsed_ms = round((time.perf_counter() - model_load_started) * 1000)
    cache_hit = bool(
        cache_info_before is not None
        and cache_info_after is not None
        and cache_info_after.hits > cache_info_before.hits
    )
    model_diagnostic = {
        "model": settings.faster_whisper_model_size,
        "device": settings.faster_whisper_device,
        "compute_type": settings.faster_whisper_compute_type,
        "cache_hit": cache_hit,
        "model_initialization_elapsed_ms": model_initialization_elapsed_ms,
        "worker_pid": os.getpid(),
    }
    logger.warning(
        "viral_asr request_id=%s stage=asr_loading outcome=model_ready model=%s device=%s compute_type=%s "
        "cache_hit=%s model_initialization_elapsed_ms=%s worker_pid=%s",
        request_id,
        settings.faster_whisper_model_size,
        settings.faster_whisper_device,
        settings.faster_whisper_compute_type,
        cache_hit,
        model_initialization_elapsed_ms,
        os.getpid(),
    )
    if model_ready_callback is not None:
        model_ready_callback(model_diagnostic)

    domain = settings.viral_asr_domain.strip().lower()
    logger.warning(
        "viral_asr request_id=%s stage=transcribe outcome=started model=%s device=%s compute_type=%s language=%s beam_size=%s vad_filter=%s word_timestamps=%s domain=%s initial_prompt=%s hotwords=%s worker_pid=%s",
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
        os.getpid(),
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
    inference_elapsed_seconds = max(0.001, time.perf_counter() - initial_started)
    logger.warning(
        "viral_asr request_id=%s stage=transcribe outcome=metrics audio_duration_seconds=%.3f "
        "inference_elapsed_seconds=%.3f real_time_factor=%.4f worker_pid=%s",
        request_id,
        expected_duration,
        inference_elapsed_seconds,
        inference_elapsed_seconds / max(expected_duration, 0.001),
        os.getpid(),
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
    return await _asr_process_manager.transcribe(audio_path, language, expected_duration)


def _asr_worker_main(command_queue, result_queue) -> None:
    while True:
        command = command_queue.get()
        if command is None:
            return
        task_id, request_id, audio_path, language, expected_duration = command
        request_token = bind_request_id(request_id)
        try:
            def report_model_ready(diagnostic: dict[str, Any]) -> None:
                result_queue.put(("model_ready", task_id, diagnostic))

            result = _transcribe_with_faster_whisper(
                Path(audio_path),
                language,
                expected_duration,
                model_ready_callback=report_model_ready,
            )
            result_queue.put(("result", task_id, result))
        except BaseException as error:
            result_queue.put(
                (
                    "result",
                    task_id,
                    ASRResult(
                        ok=False,
                        fallback_reason="ASR worker 发生未预期错误。",
                        error_code="asr_worker_failed",
                        retryable=True,
                        diagnostic=f"{type(error).__name__}: {error}"[:500],
                    ),
                )
            )
        finally:
            reset_request_id(request_token)


class _ASRProcessManager:
    def __init__(self) -> None:
        self._context = multiprocessing.get_context("spawn")
        self._state_lock = threading.Lock()
        self._process = None
        self._commands = None
        self._results = None
        self._active_task_id: str | None = None
        self._residual_worker = False
        self._model_ready = False

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            process = self._process
            return {
                "worker_alive": bool(process and process.is_alive()),
                "worker_pid": process.pid if process and process.is_alive() else None,
                "model_ready": self._model_ready,
                "task_active": self._active_task_id is not None,
                "residual_worker": self._residual_worker,
            }

    def _ensure_worker(self) -> tuple[Any, Any, int]:
        with self._state_lock:
            if self._residual_worker:
                raise RuntimeError("previous_asr_worker_residual")
            if self._process is None or not self._process.is_alive():
                self._commands = self._context.Queue()
                self._results = self._context.Queue()
                self._process = self._context.Process(
                    target=_asr_worker_main,
                    args=(self._commands, self._results),
                    name="viral-asr-worker",
                    daemon=True,
                )
                self._process.start()
                self._model_ready = False
            return self._commands, self._results, int(self._process.pid or -1)

    def _terminate_active_worker(self, task_id: str) -> bool:
        with self._state_lock:
            process = self._process
            commands = self._commands
            results = self._results
        if process is None:
            return True
        if process.is_alive():
            process.terminate()
            process.join(timeout=3)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)
        exited = not process.is_alive()
        with self._state_lock:
            self._residual_worker = not exited
            self._process = None if exited else process
            self._commands = None if exited else self._commands
            self._results = None if exited else self._results
            self._active_task_id = None
            self._model_ready = False
        if exited:
            for worker_queue in (commands, results):
                if worker_queue is not None and hasattr(worker_queue, "cancel_join_thread"):
                    worker_queue.cancel_join_thread()
                if worker_queue is not None and hasattr(worker_queue, "close"):
                    worker_queue.close()
        logger.warning(
            "viral_asr request_id=%s stage=transcribing outcome=worker_cancelled task_id=%s "
            "worker_pid=%s worker_exited=%s residual_worker=%s",
            current_request_id(),
            task_id,
            process.pid,
            exited,
            not exited,
        )
        return exited

    async def transcribe(self, audio_path: Path, language: str, expected_duration: float) -> ASRResult:
        request_id = current_request_id()
        task_id = f"{request_id}:{time.monotonic_ns()}"
        queued_at = time.perf_counter()
        try:
            commands, results, worker_pid = self._ensure_worker()
        except RuntimeError as error:
            logger.warning(
                "viral_asr request_id=%s stage=asr_loading outcome=rejected previous_task_residual=true",
                request_id,
            )
            return ASRResult(
                ok=False,
                fallback_reason="上一 ASR worker 尚未确认退出，已拒绝新任务。",
                error_code="asr_worker_residual",
                retryable=True,
                diagnostic=str(error),
            )
        with self._state_lock:
            if self._active_task_id is not None:
                return ASRResult(
                    ok=False,
                    fallback_reason="ASR worker 正在处理上一任务。",
                    error_code="asr_busy",
                    retryable=True,
                    diagnostic="worker_queue_busy",
                )
            self._active_task_id = task_id
        queue_elapsed_ms = round((time.perf_counter() - queued_at) * 1000)
        logger.warning(
            "viral_asr request_id=%s stage=asr_loading outcome=queued queue_elapsed_ms=%s "
            "worker_pid=%s previous_task_residual=false",
            request_id,
            queue_elapsed_ms,
            worker_pid,
        )
        commands.put((task_id, request_id, str(audio_path), language, expected_duration))
        deadline = current_pipeline_deadline()
        try:
            while True:
                try:
                    kind, result_task_id, payload = await asyncio.to_thread(results.get, True, 0.25)
                except queue.Empty:
                    continue
                if result_task_id != task_id:
                    continue
                if kind == "model_ready":
                    with self._state_lock:
                        self._model_ready = True
                    if deadline is not None:
                        if deadline.stage == "asr_loading":
                            deadline.finish_stage("asr_loading", **payload, queue_elapsed_ms=queue_elapsed_ms)
                        deadline.start_stage("transcribing")
                    continue
                with self._state_lock:
                    self._active_task_id = None
                return payload
        except asyncio.CancelledError:
            logger.warning(
                "viral_asr request_id=%s stage=%s outcome=cancellation_received task_id=%s worker_pid=%s",
                request_id,
                deadline.stage if deadline is not None else "transcribing",
                task_id,
                worker_pid,
            )
            exited = await asyncio.shield(asyncio.to_thread(self._terminate_active_worker, task_id))
            if not exited:
                logger.error(
                    "viral_asr request_id=%s stage=transcribing outcome=residual_worker_detected worker_pid=%s",
                    request_id,
                    worker_pid,
                )
            raise


_asr_process_manager = _ASRProcessManager()


def asr_worker_status() -> dict[str, Any]:
    return _asr_process_manager.status()
