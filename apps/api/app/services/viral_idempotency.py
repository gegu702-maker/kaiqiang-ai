from __future__ import annotations

import asyncio
from concurrent.futures import Future
from copy import deepcopy
from dataclasses import dataclass
import threading
import time
from typing import Any


IDEMPOTENCY_TTL_SECONDS = 30 * 60
IDEMPOTENCY_MAX_RECORDS = 256


@dataclass(frozen=True)
class IdempotencyOutcome:
    status_code: int
    payload: dict[str, Any]


@dataclass
class _IdempotencyRecord:
    fingerprint: str
    future: Future[IdempotencyOutcome]
    created_at: float
    completed_at: float | None = None


@dataclass(frozen=True)
class IdempotencyClaim:
    is_owner: bool
    future: Future[IdempotencyOutcome]


class IdempotencyConflict(ValueError):
    pass


class InMemoryIdempotencyStore:
    """Thread-safe, process-local idempotency storage with bounded TTL retention."""

    def __init__(
        self,
        *,
        ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS,
        max_records: int = IDEMPOTENCY_MAX_RECORDS,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_records = max_records
        self._records: dict[tuple[str, str], _IdempotencyRecord] = {}
        self._lock = threading.Lock()

    def claim(self, *, user_id: str, submission_id: str, fingerprint: str) -> IdempotencyClaim:
        key = (user_id, submission_id)
        now = time.monotonic()
        with self._lock:
            self._remove_expired(now)
            record = self._records.get(key)
            if record is not None:
                if record.fingerprint != fingerprint:
                    raise IdempotencyConflict("client_submission_id 已用于不同的请求内容。")
                return IdempotencyClaim(is_owner=False, future=record.future)

            self._make_room()
            future: Future[IdempotencyOutcome] = Future()
            self._records[key] = _IdempotencyRecord(
                fingerprint=fingerprint,
                future=future,
                created_at=now,
            )
            return IdempotencyClaim(is_owner=True, future=future)

    def complete(
        self,
        *,
        user_id: str,
        submission_id: str,
        outcome: IdempotencyOutcome,
    ) -> None:
        key = (user_id, submission_id)
        with self._lock:
            record = self._records.get(key)
            if record is None or record.future.done():
                return
            copied = IdempotencyOutcome(
                status_code=outcome.status_code,
                payload=deepcopy(outcome.payload),
            )
            record.completed_at = time.monotonic()
            record.future.set_result(copied)

    async def wait(self, claim: IdempotencyClaim) -> IdempotencyOutcome:
        outcome = await asyncio.wrap_future(claim.future)
        return IdempotencyOutcome(
            status_code=outcome.status_code,
            payload=deepcopy(outcome.payload),
        )

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def _remove_expired(self, now: float) -> None:
        expired = [
            key
            for key, record in self._records.items()
            if record.completed_at is not None and now - record.completed_at >= self._ttl_seconds
        ]
        for key in expired:
            self._records.pop(key, None)

    def _make_room(self) -> None:
        if len(self._records) < self._max_records:
            return
        completed = sorted(
            (
                (record.completed_at, key)
                for key, record in self._records.items()
                if record.completed_at is not None
            ),
            key=lambda item: item[0],
        )
        if completed:
            self._records.pop(completed[0][1], None)


viral_analysis_idempotency = InMemoryIdempotencyStore()
