from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import Any

from fastapi import HTTPException

from app.core.config import settings
from app.services.viral_diagnostics import current_request_id


logger = logging.getLogger(__name__)


STAGE_MINIMUM_BUDGET_SECONDS = {
    "transcript_correcting": lambda: settings.viral_budget_transcript_correction_seconds,
    "a_primary_generation": lambda: settings.viral_budget_a_primary_generation_seconds,
    "a_fact_review": lambda: settings.viral_budget_a_fact_review_seconds,
    "a_targeted_repair": lambda: settings.viral_budget_a_targeted_repair_seconds,
    "optional_variants": lambda: settings.viral_budget_optional_variants_seconds,
    "final_validation": lambda: settings.viral_budget_final_validation_seconds,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class PipelineDeadline:
    request_id: str
    timeout_seconds: float
    started_monotonic: float = field(default_factory=time.monotonic)
    started_at: str = field(default_factory=_utc_now)
    stage: str = "receiving"
    completed_stages: list[dict[str, Any]] = field(default_factory=list)
    stage_diagnostics: dict[str, Any] = field(default_factory=dict)
    _stage_started_monotonic: float = field(default_factory=time.monotonic)
    _stage_started_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        logger.warning(
            "viral_stage request_id=%s stage=%s outcome=started started_at=%s elapsed_ms=0 remaining_budget_ms=%s",
            self.request_id,
            self.stage,
            self._stage_started_at,
            self.remaining_budget_ms,
        )

    @property
    def elapsed_ms(self) -> int:
        return max(0, round((time.monotonic() - self.started_monotonic) * 1000))

    @property
    def remaining_budget_ms(self) -> int:
        return max(0, round(self.timeout_seconds * 1000) - self.elapsed_ms)

    def start_stage(self, stage: str) -> None:
        if self.stage == stage:
            return
        self.stage = stage
        self._stage_started_monotonic = time.monotonic()
        self._stage_started_at = _utc_now()
        logger.warning(
            "viral_stage request_id=%s stage=%s outcome=started started_at=%s elapsed_ms=%s remaining_budget_ms=%s",
            self.request_id,
            stage,
            self._stage_started_at,
            self.elapsed_ms,
            self.remaining_budget_ms,
        )

    def finish_stage(self, stage: str | None = None, **diagnostic: Any) -> dict[str, Any]:
        finished_stage = stage or self.stage
        finished_at = _utc_now()
        record = {
            "stage": finished_stage,
            "started_at": self._stage_started_at,
            "finished_at": finished_at,
            "elapsed_ms": max(0, round((time.monotonic() - self._stage_started_monotonic) * 1000)),
            "remaining_budget_ms": self.remaining_budget_ms,
        }
        if diagnostic:
            record["diagnostic"] = diagnostic
            self.stage_diagnostics[finished_stage] = diagnostic
        self.completed_stages.append(record)
        logger.warning(
            "viral_stage request_id=%s stage=%s outcome=completed started_at=%s finished_at=%s elapsed_ms=%s remaining_budget_ms=%s",
            self.request_id,
            finished_stage,
            record["started_at"],
            finished_at,
            record["elapsed_ms"],
            record["remaining_budget_ms"],
        )
        return record

    def add_diagnostic(self, stage: str, **diagnostic: Any) -> None:
        self.stage_diagnostics.setdefault(stage, {}).update(diagnostic)

    def minimum_budget_ms(self, stage: str) -> int:
        configured = STAGE_MINIMUM_BUDGET_SECONDS.get(stage)
        return max(0, int((configured() if configured else 0) * 1000))

    def ensure_budget(self, stage: str, *, minimum_budget_ms: int | None = None) -> None:
        self.start_stage(stage)
        required_ms = self.minimum_budget_ms(stage) if minimum_budget_ms is None else max(0, minimum_budget_ms)
        remaining_ms = self.remaining_budget_ms
        if remaining_ms >= required_ms:
            logger.warning(
                "viral_budget request_id=%s stage=%s outcome=accepted required_budget_ms=%s remaining_budget_ms=%s",
                self.request_id,
                stage,
                required_ms,
                remaining_ms,
            )
            return
        logger.warning(
            "viral_budget request_id=%s stage=%s outcome=rejected code=budget_insufficient required_budget_ms=%s remaining_budget_ms=%s",
            self.request_id,
            stage,
            required_ms,
            remaining_ms,
        )
        detail = self.failure_detail(
            code="budget_insufficient",
            stage=stage,
            message=_budget_message(stage),
            retryable=True,
        )
        detail["required_budget_ms"] = required_ms
        if stage == "a_fact_review":
            primary = self.stage_diagnostics.get("a_primary_generation") or {}
            detail["a_primary_chars"] = int(primary.get("actual_chars") or 0)
            detail["llm_call_count"] = int(primary.get("llm_call_count") or 0)
            detail["maximum_llm_calls"] = int(primary.get("maximum_llm_calls") or 9)
        raise HTTPException(status_code=503, detail=detail)

    def failure_detail(self, *, code: str, stage: str | None = None, message: str, retryable: bool) -> dict[str, Any]:
        return {
            "code": code,
            "stage": stage or self.stage,
            "message": message,
            "request_id": self.request_id,
            "retryable": retryable,
            "elapsed_ms": self.elapsed_ms,
            "remaining_budget_ms": self.remaining_budget_ms,
            "stage_started_at": self._stage_started_at,
            "stage_elapsed_ms": max(0, round((time.monotonic() - self._stage_started_monotonic) * 1000)),
            "completed_stages": list(self.completed_stages),
            "stage_diagnostics": dict(self.stage_diagnostics),
        }


def _budget_message(stage: str) -> str:
    if stage == "a_fact_review":
        return "ASR及主稿初稿已完成，但剩余处理预算不足，未启动事实审校。"
    return f"{stage} 开始前剩余处理预算不足，未启动该阶段。"


_current_deadline: ContextVar[PipelineDeadline | None] = ContextVar("viral_pipeline_deadline", default=None)


def bind_pipeline_deadline(deadline: PipelineDeadline) -> Token:
    return _current_deadline.set(deadline)


def reset_pipeline_deadline(token: Token) -> None:
    _current_deadline.reset(token)


def current_pipeline_deadline() -> PipelineDeadline | None:
    return _current_deadline.get()


def ensure_llm_budget(stage: str | None = None) -> None:
    deadline = current_pipeline_deadline()
    if deadline is None:
        return
    deadline.ensure_budget(stage or deadline.stage)


def new_pipeline_deadline(request_id: str) -> PipelineDeadline:
    return PipelineDeadline(request_id=request_id or current_request_id(), timeout_seconds=settings.viral_pipeline_timeout_seconds)
