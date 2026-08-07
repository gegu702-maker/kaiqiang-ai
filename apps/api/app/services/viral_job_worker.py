from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from fastapi import HTTPException
from postgrest.exceptions import APIError

from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.asr_fact_normalization import normalize_asr_for_fact_ledger
from app.services.asr_service import ASRSegment, transcribe_audio
from app.services.financial_transcript import CorrectionResult, correct_financial_transcript
from app.services.llm_provider import (
    LLMProviderError,
    LLMReplayContext,
    bind_llm_replay_context,
    reset_llm_replay_context,
)
from app.services.video_download_service import extract_audio, probe_media_duration
from app.services.viral_analyzer import analyze_viral_script
from app.services.viral_diagnostics import bind_request_id, reset_request_id
from app.services.viral_job_repository import ViralJobRepository, sanitize_error_message


logger = logging.getLogger(__name__)

PIPELINE_VERSION = "p2.37-async-v1"
STAGE_PROGRESS = {
    "media_received": 5,
    "media_extracting": 12,
    "asr_loading": 20,
    "transcribing": 38,
    "transcript_correcting": 48,
    "asr_normalizing": 55,
    "a_primary_generation": 68,
    "a_fact_review": 76,
    "a_targeted_repair": 84,
    "optional_variants": 91,
    "final_validating": 97,
    "succeeded": 100,
}


@dataclass
class StageResult:
    next_stage: str
    checkpoint: dict[str, Any]
    progress: int
    result: dict[str, Any] | None = None
    quality: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None


class StageExecutor(Protocol):
    async def execute(self, job: dict[str, Any]) -> StageResult: ...


class StageFailure(RuntimeError):
    def __init__(self, *, category: str, code: str, message: str, retryable: bool):
        super().__init__(message)
        self.category = category
        self.code = code
        self.retryable = retryable


def _segments(values: list[dict[str, Any]]) -> list[ASRSegment]:
    return [
        ASRSegment(start=float(item["start"]), end=float(item["end"]), text=str(item["text"]))
        for item in values
    ]


def _segment_dicts(values: list[ASRSegment]) -> list[dict[str, Any]]:
    return [{"start": item.start, "end": item.end, "text": item.text} for item in values]


def _expired(value: object, *, now: datetime) -> bool:
    if not value:
        return False
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed <= now


class ProductionViralStageExecutor:
    """Durable media/ASR checkpoints; model quality logic remains in viral_analyzer."""

    def __init__(self, repository: ViralJobRepository):
        self.repository = repository
        self.worker_owner = ""
        self.lease_seconds = 60

    def configure_checkpointing(self, *, worker_owner: str, lease_seconds: int) -> None:
        self.worker_owner = worker_owner
        self.lease_seconds = lease_seconds

    def _persist_checkpoint(
        self,
        *,
        job: dict[str, Any],
        stage: str,
        checkpoint: dict[str, Any],
    ) -> None:
        if not self.worker_owner:
            raise RuntimeError("Checkpoint owner is not configured.")
        state = self.repository.checkpoint_progress(
            job=job,
            worker_owner=self.worker_owner,
            stage=stage,
            checkpoint=checkpoint,
            lease_seconds=self.lease_seconds,
        )
        job["revision"] = int(state["new_revision"])
        job["stage"] = stage
        job["status"] = str(state.get("observed_status") or job.get("status") or "running")
        if job["status"] == "cancel_requested":
            raise StageFailure(
                category="cancelled",
                code="cancelled_by_user",
                message="任务已取消。",
                retryable=False,
            )

    async def execute(self, job: dict[str, Any]) -> StageResult:
        stage = str(job["stage"])
        checkpoint = dict(job.get("checkpoint") or {})
        if stage == "media_received":
            return StageResult("media_extracting", checkpoint, STAGE_PROGRESS[stage])
        if stage == "media_extracting":
            return await self._extract(job, checkpoint)
        if stage == "asr_loading":
            return StageResult("transcribing", checkpoint, STAGE_PROGRESS[stage])
        if stage == "transcribing":
            return await self._transcribe(job, checkpoint)
        if stage == "transcript_correcting":
            return await self._correct(job, checkpoint)
        if stage == "asr_normalizing":
            return await self._normalize(job, checkpoint)
        if stage in {"a_primary_generation", "a_fact_review", "a_targeted_repair", "optional_variants"}:
            return await self._analyze(job, checkpoint)
        if stage == "final_validating":
            result = checkpoint.get("analysis")
            if not isinstance(result, dict) or not result.get("rewrites"):
                raise StageFailure(
                    category="quality",
                    code="final_result_invalid",
                    message="最终结果缺少有效改写稿。",
                    retryable=False,
                )
            diagnostics = dict(result.get("diagnostics") or {})
            return StageResult(
                "succeeded",
                checkpoint,
                100,
                result=result,
                quality={
                    "target_min_chars": diagnostics.get("target_min_chars"),
                    "target_max_chars": diagnostics.get("target_max_chars"),
                    "rewrite_actual_chars": diagnostics.get("rewrite_actual_chars"),
                    "hard_violations": diagnostics.get("hard_violations_after", []),
                },
                provenance={"value": result.get("provenance", "model")},
            )
        raise StageFailure(
            category="state",
            code="unknown_job_stage",
            message="任务阶段不可识别。",
            retryable=False,
        )

    async def _extract(self, job: dict[str, Any], checkpoint: dict[str, Any]) -> StageResult:
        if checkpoint.get("audio_object_path") and checkpoint.get("duration_seconds") is not None:
            return StageResult("asr_loading", checkpoint, STAGE_PROGRESS["media_extracting"])
        bucket = str(job.get("input_bucket") or settings.viral_job_artifact_bucket)
        source_path = str(job.get("input_object_path") or "")
        if not source_path:
            raise StageFailure(category="storage", code="input_missing", message="上传文件引用缺失。", retryable=False)
        with tempfile.TemporaryDirectory(prefix="viral-job-") as tmp:
            work = Path(tmp)
            video = work / "source.bin"
            await asyncio.to_thread(
                self.repository.download_file,
                bucket=bucket,
                object_path=source_path,
                destination=video,
            )
            duration = await probe_media_duration(video)
            if duration > settings.viral_max_video_duration_seconds:
                raise StageFailure(category="quality", code="video_too_long", message="视频时长超过允许范围。", retryable=False)
            audio = await extract_audio(video, work)
            audio_object = f"{job['user_id']}/{job['id']}/audio/{PIPELINE_VERSION}.wav"
            with audio.open("rb") as source:
                await asyncio.to_thread(
                    self.repository.upload_file,
                    bucket=bucket,
                    object_path=audio_object,
                    source=source,
                    content_type="audio/wav",
                    upsert=True,
                )
        checkpoint.update({"duration_seconds": duration, "audio_object_path": audio_object})
        self._persist_checkpoint(job=job, stage="media_extracting", checkpoint=checkpoint)
        return StageResult("asr_loading", checkpoint, STAGE_PROGRESS["media_extracting"])

    async def _transcribe(self, job: dict[str, Any], checkpoint: dict[str, Any]) -> StageResult:
        if isinstance(checkpoint.get("asr"), dict) and checkpoint["asr"].get("transcript"):
            return StageResult("transcript_correcting", checkpoint, STAGE_PROGRESS["transcribing"])
        bucket = str(job.get("input_bucket") or settings.viral_job_artifact_bucket)
        audio_object = str(checkpoint.get("audio_object_path") or "")
        if not audio_object:
            raise StageFailure(category="checkpoint", code="audio_checkpoint_missing", message="音频checkpoint缺失。", retryable=False)
        with tempfile.TemporaryDirectory(prefix="viral-asr-") as tmp:
            audio = Path(tmp) / "audio.wav"
            await asyncio.to_thread(
                self.repository.download_file,
                bucket=bucket,
                object_path=audio_object,
                destination=audio,
            )
            asr = await transcribe_audio(
                audio,
                str(checkpoint.get("language") or "zh"),
                float(checkpoint.get("duration_seconds") or 0),
            )
        if not asr.ok:
            raise StageFailure(
                category="resource" if asr.retryable else "quality",
                code=asr.error_code or "asr_failed",
                message=asr.fallback_reason or "转写失败。",
                retryable=asr.retryable,
            )
        checkpoint["asr"] = {
            "transcript": asr.transcript,
            "segments": _segment_dicts(asr.segments or []),
            "coverage_seconds": asr.coverage_seconds,
            "provider": asr.provider,
        }
        self._persist_checkpoint(job=job, stage="transcribing", checkpoint=checkpoint)
        return StageResult("transcript_correcting", checkpoint, STAGE_PROGRESS["transcribing"])

    async def _correct(self, job: dict[str, Any], checkpoint: dict[str, Any]) -> StageResult:
        if isinstance(checkpoint.get("correction"), dict) and checkpoint["correction"].get("transcript"):
            return StageResult("asr_normalizing", checkpoint, STAGE_PROGRESS["transcript_correcting"])
        raw = dict(checkpoint.get("asr") or {})
        segments = _segments(list(raw.get("segments") or []))
        if settings.viral_asr_domain.strip().lower() == "financial":
            correction = await correct_financial_transcript(segments, str(checkpoint.get("language") or "zh"))
        else:
            correction = CorrectionResult(
                corrected_transcript=str(raw.get("transcript") or ""),
                corrected_segments=segments,
                corrections=[],
                review_segments=[],
                quality_passed=True,
                provider="none",
            )
        if not correction.quality_passed:
            raise StageFailure(category="quality", code="transcript_quality_insufficient", message="转写校正质量不足。", retryable=True)
        checkpoint["correction"] = {
            "transcript": correction.corrected_transcript,
            "segments": _segment_dicts(correction.corrected_segments),
            "correction_count": len(correction.corrections),
            "provider": correction.provider,
        }
        self._persist_checkpoint(job=job, stage="transcript_correcting", checkpoint=checkpoint)
        return StageResult("asr_normalizing", checkpoint, STAGE_PROGRESS["transcript_correcting"])

    async def _normalize(self, job: dict[str, Any], checkpoint: dict[str, Any]) -> StageResult:
        if isinstance(checkpoint.get("normalization"), dict) and checkpoint["normalization"].get("transcript"):
            return StageResult("a_primary_generation", checkpoint, STAGE_PROGRESS["asr_normalizing"])
        correction = dict(checkpoint.get("correction") or {})
        raw = dict(checkpoint.get("asr") or {})
        normalized = normalize_asr_for_fact_ledger(
            _segments(list(correction.get("segments") or [])),
            str(correction.get("transcript") or ""),
            raw_transcript=str(raw.get("transcript") or ""),
            raw_segment_count=len(raw.get("segments") or []),
        )
        checkpoint["normalization"] = {
            "transcript": normalized.normalized_text,
            "sentences": [item.as_dict() for item in normalized.normalized_sentences],
            "diagnostics": normalized.diagnostics,
        }
        self._persist_checkpoint(job=job, stage="asr_normalizing", checkpoint=checkpoint)
        return StageResult("a_primary_generation", checkpoint, STAGE_PROGRESS["asr_normalizing"])

    async def _analyze(self, job: dict[str, Any], checkpoint: dict[str, Any]) -> StageResult:
        normalized = dict(checkpoint.get("normalization") or {})
        asr = dict(checkpoint.get("asr") or {})
        replay_cache = checkpoint.setdefault("model_replay", {})
        if not isinstance(replay_cache, dict):
            raise StageFailure(
                category="checkpoint",
                code="model_checkpoint_invalid",
                message="模型checkpoint格式无效。",
                retryable=False,
            )

        def persist_replay(_key: str, stage: str) -> None:
            self._persist_checkpoint(job=job, stage=stage, checkpoint=checkpoint)

        replay_token = bind_llm_replay_context(
            LLMReplayContext(cache=replay_cache, persist=persist_replay)
        )
        try:
            analysis = await analyze_viral_script(
                self.repository.supabase,
                user_id=str(job["user_id"]),
                email=str(checkpoint.get("email") or ""),
                source_url=str(checkpoint.get("source_url") or ""),
                raw_script=str(normalized.get("transcript") or ""),
                industry=str(checkpoint.get("industry") or "personal_brand"),
                language=str(checkpoint.get("language") or "zh"),
                rewrite_length=str(checkpoint.get("rewrite_length") or "match_source"),
                effective_speech_seconds=float(asr.get("coverage_seconds") or 0),
                source_fact_sentences=list(normalized.get("sentences") or []),
                persist_side_effects=False,
            )
        finally:
            reset_llm_replay_context(replay_token)
        checkpoint["analysis"] = analysis
        return StageResult("final_validating", checkpoint, STAGE_PROGRESS["optional_variants"])


def classify_failure(error: BaseException) -> StageFailure:
    if isinstance(error, StageFailure):
        return error
    if isinstance(error, LLMProviderError):
        text = str(error).lower()
        contract = any(marker in text for marker in ("json", "schema", "contract", "format"))
        return StageFailure(
            category="model_contract" if contract else "network",
            code="model_contract_error" if contract else "model_transport_error",
            message="模型响应格式异常。" if contract else "模型服务暂时不可用。",
            retryable=True,
        )
    if isinstance(error, (TimeoutError, asyncio.TimeoutError, httpx_error_types())):
        return StageFailure(category="network", code="stage_timeout", message="阶段执行超时。", retryable=True)
    if isinstance(error, HTTPException):
        return StageFailure(category="quality", code="analysis_rejected", message=sanitize_error_message(error.detail), retryable=False)
    if isinstance(error, APIError):
        return StageFailure(category="database", code="database_error", message="任务状态存储失败。", retryable=True)
    return StageFailure(category="internal", code="internal_error", message="任务处理失败。", retryable=False)


def httpx_error_types() -> type[Exception]:
    # Kept as a function so tests can replace network clients without importing internals.
    import httpx

    return httpx.HTTPError


class ViralJobWorker:
    def __init__(
        self,
        repository: ViralJobRepository,
        executor: StageExecutor,
        *,
        worker_owner: str | None = None,
        lease_seconds: int = 60,
        heartbeat_seconds: int = 15,
        stage_timeout_seconds: int = 180,
    ):
        self.repository = repository
        self.executor = executor
        self.worker_owner = worker_owner or f"viral-{uuid4().hex}"
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.stage_timeout_seconds = stage_timeout_seconds
        configure = getattr(self.executor, "configure_checkpointing", None)
        if callable(configure):
            configure(worker_owner=self.worker_owner, lease_seconds=self.lease_seconds)

    async def run_once(self) -> bool:
        job = await asyncio.to_thread(
            self.repository.claim,
            worker_owner=self.worker_owner,
            lease_seconds=self.lease_seconds,
        )
        if not job:
            return False
        await self._run_claimed(job)
        return True

    def run_cleanup_once(self) -> bool:
        cleanup_owner = f"{self.worker_owner}-cleanup"
        job = self.repository.claim_cleanup(worker_owner=cleanup_owner, lease_seconds=120)
        if not job:
            return False
        now = datetime.now(UTC)
        clear_input = _expired(job.get("input_expires_at"), now=now)
        clear_checkpoint = _expired(job.get("checkpoint_expires_at"), now=now)
        clear_result = _expired(job.get("result_expires_at"), now=now)
        purge = _expired(job.get("purge_after"), now=now)
        checkpoint = dict(job.get("checkpoint") or {})
        paths: list[str] = []
        if clear_input or purge:
            paths.append(str(job.get("input_object_path") or ""))
        if clear_checkpoint or purge:
            paths.append(str(checkpoint.get("audio_object_path") or ""))
        try:
            self.repository.remove_objects(
                bucket=str(job.get("input_bucket") or settings.viral_job_artifact_bucket),
                object_paths=paths,
            )
        except Exception:
            self.repository.finish_cleanup(
                job=job,
                worker_owner=cleanup_owner,
                clear_input=False,
                clear_checkpoint=False,
                clear_result=False,
                purge=False,
                success=False,
            )
            raise
        accepted = self.repository.finish_cleanup(
            job=job,
            worker_owner=cleanup_owner,
            clear_input=clear_input or purge,
            clear_checkpoint=clear_checkpoint or purge,
            clear_result=clear_result or purge,
            purge=purge,
            success=True,
        )
        if not accepted:
            logger.warning("Late viral cleanup result rejected job_id=%s", job["id"])
        return accepted

    async def _run_claimed(self, job: dict[str, Any]) -> None:
        token = bind_request_id(str(job.get("request_id") or f"viral_{job['id']}"))
        try:
            while str(job.get("status")) in {"running", "cancel_requested"}:
                if job.get("status") == "cancel_requested":
                    await asyncio.to_thread(
                        self.repository.finish_stage,
                        job=job,
                        worker_owner=self.worker_owner,
                        outcome="cancelled",
                        next_status="cancelled",
                        next_stage="cancelled",
                        progress=int(job.get("progress") or 0),
                        checkpoint=job.get("checkpoint"),
                        error_class="cancelled",
                        error_code="cancelled_by_user",
                        safe_error_message="任务已取消。",
                        elapsed_ms=0,
                    )
                    return
                started = time.perf_counter()
                try:
                    stage_result = await self._execute_with_heartbeat(job)
                    terminal = stage_result.next_stage == "succeeded"
                    accepted = await asyncio.to_thread(
                        self.repository.finish_stage,
                        job=job,
                        worker_owner=self.worker_owner,
                        outcome="succeeded",
                        next_status="succeeded" if terminal else "running",
                        next_stage=stage_result.next_stage,
                        progress=stage_result.progress,
                        checkpoint=stage_result.checkpoint,
                        result=stage_result.result,
                        quality=stage_result.quality,
                        provenance=stage_result.provenance,
                        elapsed_ms=round((time.perf_counter() - started) * 1000),
                    )
                    if not accepted:
                        logger.warning("Late viral worker result rejected job_id=%s", job["id"])
                        return
                    if terminal:
                        return
                    fresh = await asyncio.to_thread(self.repository.get_internal, str(job["id"]))
                    if not fresh or fresh.get("lease_owner") != self.worker_owner:
                        return
                    job = fresh
                except asyncio.CancelledError:
                    raise
                except BaseException as error:
                    failure = classify_failure(error)
                    attempts = int(job.get("attempt") or 1)
                    cancelled = failure.category == "cancelled"
                    retryable = (
                        failure.retryable
                        and not cancelled
                        and attempts < int(job.get("max_attempts") or 3)
                    )
                    delay = min(120, 5 * (2 ** max(0, attempts - 1)))
                    await asyncio.to_thread(
                        self.repository.finish_stage,
                        job=job,
                        worker_owner=self.worker_owner,
                        outcome="cancelled" if cancelled else "failed",
                        next_status="cancelled" if cancelled else "retry_wait" if retryable else "failed",
                        next_stage="cancelled" if cancelled else str(job.get("stage") or "failed"),
                        progress=int(job.get("progress") or 0),
                        checkpoint=job.get("checkpoint"),
                        error_class=failure.category,
                        error_code=failure.code,
                        safe_error_message=str(failure),
                        retryable=retryable,
                        next_retry_at=(datetime.now(UTC) + timedelta(seconds=delay)).isoformat() if retryable else None,
                        elapsed_ms=round((time.perf_counter() - started) * 1000),
                    )
                    return
        finally:
            reset_request_id(token)

    async def _execute_with_heartbeat(self, job: dict[str, Any]) -> StageResult:
        task = asyncio.create_task(self.executor.execute(job))
        deadline = time.monotonic() + self.stage_timeout_seconds
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    raise TimeoutError("stage deadline exceeded")
                done, _ = await asyncio.wait(
                    {task}, timeout=min(self.heartbeat_seconds, remaining)
                )
                if task in done:
                    return task.result()
                try:
                    heartbeat = await asyncio.to_thread(
                        self.repository.heartbeat,
                        job_id=str(job["id"]),
                        worker_owner=self.worker_owner,
                        revision=int(job["revision"]),
                        lease_seconds=self.lease_seconds,
                    )
                    job["revision"] = int(heartbeat["new_revision"])
                    if heartbeat.get("observed_status") == "cancel_requested":
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                        fresh = await asyncio.to_thread(self.repository.get_internal, str(job["id"]))
                        if fresh:
                            job.update(fresh)
                        raise StageFailure(
                            category="cancelled",
                            code="cancelled_by_user",
                            message="任务已取消。",
                            retryable=False,
                        )
                except RuntimeError:
                    fresh = await asyncio.to_thread(self.repository.get_internal, str(job["id"]))
                    if fresh and fresh.get("status") == "cancel_requested" and fresh.get("lease_owner") == self.worker_owner:
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                        job.update(fresh)
                        raise StageFailure(
                            category="cancelled",
                            code="cancelled_by_user",
                            message="任务已取消。",
                            retryable=False,
                        )
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    raise
        finally:
            if not task.done():
                task.cancel()


async def viral_job_worker_loop() -> None:
    if not settings.viral_async_jobs_enabled:
        return
    repository = ViralJobRepository(get_supabase())
    worker = ViralJobWorker(
        repository,
        ProductionViralStageExecutor(repository),
        lease_seconds=settings.viral_job_lease_seconds,
        heartbeat_seconds=settings.viral_job_heartbeat_seconds,
        stage_timeout_seconds=settings.viral_job_stage_timeout_seconds,
    )
    while True:
        try:
            worked = await worker.run_once()
            if not worked:
                worked = await asyncio.to_thread(worker.run_cleanup_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Viral async worker loop failed")
            worked = False
        await asyncio.sleep(0 if worked else settings.viral_job_poll_seconds)
