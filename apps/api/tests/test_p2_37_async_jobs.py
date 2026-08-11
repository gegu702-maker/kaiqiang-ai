from __future__ import annotations

import asyncio
import hashlib
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from io import BytesIO
import json
from pathlib import Path
from threading import Lock
from typing import Any

import pytest
from starlette.datastructures import UploadFile

from app.core.config import settings
from app.services.llm_provider import (
    LLMProvider,
    LLMReplayContext,
    bind_llm_replay_context,
    reset_llm_replay_context,
)
from app.services.viral_job_repository import (
    SAFE_JOB_COLUMNS,
    parameter_version,
    sanitize_error_message,
)
from app.services.viral_job_worker import (
    ProductionViralStageExecutor,
    STAGE_PROGRESS,
    StageFailure,
    StageResult,
    ViralJobWorker,
)
import app.services.viral_job_worker as worker_module
import app.api.viral as viral_api


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase" / "p2_37_viral_async_jobs_preview.sql"
ROLLBACK = ROOT / "supabase" / "p2_37_viral_async_jobs_preview_rollback.sql"
WEB_CLIENT = ROOT / "apps" / "web" / "components" / "ViralAnalyzerClient.tsx"
WEB_API = ROOT / "apps" / "web" / "lib" / "api.ts"


def _job(**overrides: Any) -> dict[str, Any]:
    value = {
        "id": "00000000-0000-0000-0000-000000000001",
        "request_id": "viral_request_0001",
        "user_id": "00000000-0000-0000-0000-000000000002",
        "pipeline_version": "p2.37-async-v1",
        "status": "pending",
        "stage": "media_received",
        "progress": 5,
        "attempt": 0,
        "max_attempts": 3,
        "revision": 0,
        "lease_owner": None,
        "lease_expires_at": None,
        "checkpoint": {"industry": "knowledge", "language": "zh"},
    }
    value.update(overrides)
    return value


class FakeRepository:
    def __init__(self, job: dict[str, Any] | None = None):
        self.job = deepcopy(job) if job else None
        self.lock = Lock()
        self.finishes: list[dict[str, Any]] = []
        self.cleanup_job: dict[str, Any] | None = None
        self.removed_paths: list[str] = []
        self.cleanup_finishes: list[dict[str, Any]] = []

    def claim(self, *, worker_owner: str, lease_seconds: int) -> dict[str, Any] | None:
        del lease_seconds
        with self.lock:
            if not self.job or self.job["status"] not in {"pending", "retry_wait"}:
                return None
            self.job.update(
                status="running",
                lease_owner=worker_owner,
                lease_expires_at="2999-01-01T00:00:00+00:00",
                attempt=int(self.job["attempt"]) + 1,
                revision=int(self.job["revision"]) + 1,
            )
            return deepcopy(self.job)

    def heartbeat(self, *, job_id: str, worker_owner: str, revision: int, lease_seconds: int) -> dict[str, Any]:
        del job_id, lease_seconds
        if not self.job or self.job["lease_owner"] != worker_owner or self.job["revision"] != revision:
            raise RuntimeError("lost")
        self.job["revision"] += 1
        return {"accepted": True, "new_revision": self.job["revision"], "observed_status": self.job["status"]}

    def finish_stage(self, **kwargs: Any) -> bool:
        claimed = kwargs["job"]
        if (
            not self.job
            or self.job["lease_owner"] != kwargs["worker_owner"]
            or self.job["revision"] != claimed["revision"]
            or self.job["status"] in {"succeeded", "failed", "cancelled"}
        ):
            return False
        self.finishes.append(deepcopy(kwargs))
        self.job.update(
            status=kwargs["next_status"],
            stage=kwargs["next_stage"],
            progress=kwargs["progress"],
            checkpoint=deepcopy(kwargs.get("checkpoint")),
            revision=self.job["revision"] + 1,
        )
        if kwargs["next_status"] != "running":
            self.job["lease_owner"] = None
        return True

    def get_internal(self, job_id: str) -> dict[str, Any] | None:
        del job_id
        return deepcopy(self.job)

    def claim_cleanup(self, *, worker_owner: str, lease_seconds: int) -> dict[str, Any] | None:
        del lease_seconds
        if not self.cleanup_job:
            return None
        self.cleanup_job["cleanup_lease_owner"] = worker_owner
        self.cleanup_job["revision"] = int(self.cleanup_job.get("revision") or 0) + 1
        claimed = deepcopy(self.cleanup_job)
        self.cleanup_job = None
        return claimed

    def remove_objects(self, *, bucket: str, object_paths: list[str]) -> None:
        assert bucket == "viral-job-artifacts-preview"
        self.removed_paths.extend(object_paths)

    def finish_cleanup(self, **kwargs: Any) -> bool:
        self.cleanup_finishes.append(deepcopy(kwargs))
        return True


class ScriptedExecutor:
    def __init__(self, sequence: list[StageResult | BaseException]):
        self.sequence = list(sequence)
        self.calls: list[dict[str, Any]] = []

    async def execute(self, job: dict[str, Any]) -> StageResult:
        self.calls.append(deepcopy(job))
        value = self.sequence.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


def run(worker: ViralJobWorker) -> bool:
    return asyncio.run(worker.run_once())


def test_parameter_version_is_stable_and_parameter_sensitive() -> None:
    first = parameter_version(params_hash="a" * 64, pipeline_version="v1")
    assert first == parameter_version(params_hash="a" * 64, pipeline_version="v1")
    assert first != parameter_version(params_hash="b" * 64, pipeline_version="v1")
    assert first != parameter_version(params_hash="a" * 64, pipeline_version="v2")


def test_job_initiation_accepts_12_2_mb_and_returns_clear_413_over_50_mib(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted = viral_api.ViralJobInitiateRequest(
        filename="synthetic.mp4",
        file_size=12_200_000,
        file_fingerprint="a" * 64,
    )
    assert accepted.file_size == 12_200_000
    oversized = viral_api.ViralJobInitiateRequest(
            filename="synthetic.mp4",
            file_size=50 * 1024 * 1024 + 1,
            file_fingerprint="a" * 64,
    )
    monkeypatch.setattr(settings, "viral_async_jobs_enabled", True)
    monkeypatch.setattr(
        viral_api,
        "get_authenticated_user",
        lambda supabase, token: {"id": "00000000-0000-0000-0000-000000000999", "email": "preview@example.invalid"},
    )
    with pytest.raises(viral_api.HTTPException) as captured:
        asyncio.run(viral_api.create_or_reuse_viral_job(payload=oversized, token="mock", supabase=object()))  # type: ignore[arg-type]
    assert captured.value.status_code == 413
    assert captured.value.detail["code"] == "upload_too_large"


def test_job_create_api_returns_202_and_reuses_matching_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: dict[tuple[str, str, str], dict[str, Any]] = {}
    uploads = 0

    class ApiRepository:
        def __init__(self, supabase: object):
            del supabase

        def create_or_reuse(self, **kwargs: Any) -> dict[str, Any]:
            key = (
                kwargs["user_id"],
                kwargs["fingerprint"],
                kwargs["parameter_version_value"],
            )
            if key in records:
                return {"job_id": records[key]["id"], "reused": True, "job_status": records[key]["status"]}
            job = {
                "id": "00000000-0000-0000-0000-000000000123",
                "request_id": kwargs["request_id"],
                "status": "uploading",
            }
            records[key] = job
            return {"job_id": job["id"], "reused": False, "job_status": "uploading"}

        def upload_file(self, **kwargs: Any) -> None:
            nonlocal uploads
            uploads += 1
            assert kwargs["bucket"] == "viral-job-artifacts-preview"
            assert kwargs["source"].read() == b"synthetic-not-a-real-video"

        def prepare_upload(self, **kwargs: Any) -> None:
            assert kwargs["object_path"].startswith(
                "00000000-0000-0000-0000-000000000999/00000000-0000-0000-0000-000000000123/input/"
            )
            for job in records.values():
                if job["id"] == kwargs["job_id"]:
                    job.update({
                        "user_id": kwargs["user_id"],
                        "input_bucket": kwargs["bucket"],
                        "input_object_path": kwargs["object_path"],
                        "checkpoint": kwargs["checkpoint"],
                        "file_fingerprint": next(key[1] for key, value in records.items() if value is job),
                    })

        def mark_uploaded(self, **kwargs: Any) -> dict[str, Any]:
            for job in records.values():
                if job["id"] == kwargs["job_id"]:
                    job["status"] = "pending"
                    return job
            raise AssertionError("missing job")

        def get_for_user(self, *, job_id: str, user_id: str) -> dict[str, Any] | None:
            del user_id
            return next((job for job in records.values() if job["id"] == job_id), None)

        def get_internal_for_user(self, *, job_id: str, user_id: str) -> dict[str, Any] | None:
            return next((job for job in records.values() if job["id"] == job_id and job["user_id"] == user_id), None)

        def fail_upload(self, **kwargs: Any) -> None:
            raise AssertionError(f"unexpected upload failure: {kwargs}")

    monkeypatch.setattr(settings, "viral_async_jobs_enabled", True)
    monkeypatch.setattr(viral_api, "ViralJobRepository", ApiRepository)
    monkeypatch.setattr(
        viral_api,
        "get_authenticated_user",
        lambda supabase, token: {"id": "00000000-0000-0000-0000-000000000999", "email": "preview@example.invalid"},
    )

    content = b"synthetic-not-a-real-video"
    fingerprint = hashlib.sha256(content).hexdigest()

    async def create() -> dict[str, Any]:
        response = await viral_api.create_or_reuse_viral_job(
            payload=viral_api.ViralJobInitiateRequest(
                filename="synthetic.mp4",
                file_size=len(content),
                content_type="video/mp4",
                file_fingerprint=fingerprint,
                industry="knowledge",
                language="zh",
                rewrite_length="match_source",
            ),
            token="mock-token",
            supabase=object(),  # type: ignore[arg-type]
        )
        assert response.status_code == 202
        return json.loads(response.body)

    first = asyncio.run(create())
    assert first["status"] == "uploading"
    assert first["upload_required"] is True
    assert uploads == 0

    async def upload() -> dict[str, Any]:
        response = await viral_api.upload_viral_job_file(
            job_id=first["job_id"],
            video_file=UploadFile(filename="synthetic.mp4", file=BytesIO(content)),
            token="mock-token",
            supabase=object(),  # type: ignore[arg-type]
        )
        assert response.status_code == 202
        return json.loads(response.body)

    uploaded = asyncio.run(upload())
    second = asyncio.run(create())
    assert first["job_id"] == second["job_id"]
    assert first["request_id"] == second["request_id"]
    assert first["reused"] is False
    assert second["reused"] is True
    assert uploaded["status"] == "pending"
    assert second["upload_required"] is False
    assert uploads == 1


def test_artifact_upload_failure_keeps_uploading_job_and_returns_safe_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"synthetic-upload-failure"
    job = {
        "id": "00000000-0000-0000-0000-000000000123",
        "user_id": "00000000-0000-0000-0000-000000000999",
        "request_id": "request-safe",
        "status": "uploading",
        "file_fingerprint": hashlib.sha256(content).hexdigest(),
        "input_bucket": "viral-job-artifacts-preview",
        "input_object_path": "private/internal/path.mp4",
        "checkpoint": {"expected_file_size": len(content), "content_type": "video/mp4"},
    }

    class FailingRepository:
        def __init__(self, supabase: object):
            del supabase

        def get_internal_for_user(self, **kwargs: Any) -> dict[str, Any]:
            assert kwargs["job_id"] == job["id"]
            assert kwargs["user_id"] == job["user_id"]
            return job

        def upload_file(self, **kwargs: Any) -> None:
            assert kwargs["upsert"] is True
            raise RuntimeError("synthetic storage outage")

        def mark_uploaded(self, **kwargs: Any) -> None:
            raise AssertionError("failed storage upload must not enter pending")

    monkeypatch.setattr(settings, "viral_async_jobs_enabled", True)
    monkeypatch.setattr(viral_api, "ViralJobRepository", FailingRepository)
    monkeypatch.setattr(
        viral_api,
        "get_authenticated_user",
        lambda supabase, token: {"id": job["user_id"], "email": "preview@example.invalid"},
    )
    with pytest.raises(viral_api.HTTPException) as captured:
        asyncio.run(viral_api.upload_viral_job_file(
            job_id=job["id"],
            video_file=UploadFile(filename="synthetic.mp4", file=BytesIO(content)),
            token="mock",
            supabase=object(),  # type: ignore[arg-type]
        ))
    assert captured.value.status_code == 503
    assert captured.value.detail == {
        "code": "artifact_upload_failed",
        "stage": "uploading",
        "message": "上传暂时失败，任务已保留。",
        "retryable": True,
        "request_id": "request-safe",
        "job_id": job["id"],
    }
    assert job["status"] == "uploading"


def test_safe_error_redacts_secrets_and_internal_paths() -> None:
    value = sanitize_error_message("token=abc123 C:\\private\\video.mp4")
    assert "abc123" not in value
    assert "private" not in value


def test_safe_job_columns_exclude_internal_state() -> None:
    for forbidden in ("checkpoint", "input_object_path", "lease_owner", "artifact_manifest"):
        assert forbidden not in SAFE_JOB_COLUMNS.split(",")


def test_migration_only_creates_new_job_tables() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table public.viral_analysis_jobs" in sql
    assert "create table public.viral_analysis_job_stage_runs" in sql
    assert "alter table public.profiles" not in sql
    assert "alter table public.user_quotas" not in sql
    assert "delete from public.profiles" not in sql
    assert "delete from public.user_quotas" not in sql
    assert "truncate" not in sql


def test_migration_enforces_user_read_only_and_service_role_writes() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert 'using (auth.uid() = user_id)' in sql
    assert "revoke all on public.viral_analysis_jobs from anon, authenticated" in sql
    assert "grant select (" in sql
    assert "checkpoint" not in sql.split("grant select (", 1)[1].split(") on public.viral_analysis_jobs", 1)[0]


def test_private_bucket_policy_has_no_anon_or_authenticated_access() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    policy = sql.split('create policy "Service role manages preview viral artifacts"', 1)[1]
    assert "to service_role" in policy
    assert "to anon" not in policy
    assert "to authenticated" not in policy


def test_failed_and_cancelled_are_excluded_from_reuse_constraint() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    predicate = sql.split("viral_jobs_reusable_identity_uidx", 1)[1].split(";", 1)[0]
    assert "succeeded" in predicate
    assert "retry_wait" in predicate
    assert "'failed'" not in predicate
    assert "'cancelled'" not in predicate


def test_cleanup_has_its_own_persistent_claim() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "claim_viral_analysis_cleanup" in sql
    assert "cleanup_lease_owner" in sql
    assert "for update skip locked" in sql
    assert "finish_viral_analysis_cleanup" in sql
    assert "j.status in ('uploading', 'succeeded', 'failed', 'cancelled')" in sql


def test_abandoned_upload_is_failed_before_identity_is_reused() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    create_body = sql.split("create function public.create_or_reuse_viral_analysis_job", 1)[1].split("$$;", 1)[0]
    assert "error_code = 'upload_abandoned'" in create_body
    assert "created_at <= now() - interval '15 minutes'" in create_body


def test_model_checkpoint_rpc_is_lease_and_revision_guarded() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    body = sql.split("create function public.checkpoint_viral_analysis_job", 1)[1].split("$$;", 1)[0]
    assert "v_job.lease_owner is distinct from p_worker_owner" in body
    assert "v_job.revision <> p_expected_revision" in body
    assert "v_job.lease_expires_at <= now()" in body
    assert "checkpoint = p_checkpoint" in body


def test_stage_history_references_authoritative_checkpoint_without_copying_it() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    finish_body = sql.split("create function public.finish_viral_analysis_stage", 1)[1].split("$$;", 1)[0]
    values = finish_body.split(") values (", 1)[1]
    assert "p_output_version, null" in values
    assert "inline:viral_analysis_jobs/" in values


def test_cancel_request_is_atomic_and_service_role_only() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    body = sql.split("create function public.request_cancel_viral_analysis_job", 1)[1].split("$$;", 1)[0]
    assert "update public.viral_analysis_jobs" in body
    assert "else 'cancel_requested'" in body
    assert "and j.user_id = p_user_id" in body
    assert "revoke all on function public.request_cancel_viral_analysis_job(uuid, uuid)" in sql


def test_usage_is_recorded_once_inside_terminal_job_transaction() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    finish_body = sql.split("create function public.finish_viral_analysis_stage", 1)[1].split("$$;", 1)[0]
    assert "p_next_status = 'succeeded' and not v_job.usage_recorded" in finish_body
    assert "insert into public.usage_logs" in finish_body
    assert "usage_recorded = case when p_next_status = 'succeeded' then true" in finish_body
    worker_source = (ROOT / "apps" / "api" / "app" / "services" / "viral_job_worker.py").read_text(encoding="utf-8")
    assert "persist_side_effects=False" in worker_source


def test_cleanup_removes_only_expired_artifacts_and_uses_cas_completion() -> None:
    expired = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    repository = FakeRepository()
    repository.cleanup_job = _job(
        status="succeeded",
        input_bucket="viral-job-artifacts-preview",
        input_object_path="user/job/input/video.mp4",
        input_expires_at=expired,
        checkpoint_expires_at=future,
        result_expires_at=future,
        purge_after=future,
        checkpoint={"audio_object_path": "user/job/audio/file.wav"},
    )
    worker = ViralJobWorker(repository, ScriptedExecutor([]), worker_owner="one")
    assert worker.run_cleanup_once() is True
    assert repository.removed_paths == ["user/job/input/video.mp4"]
    finish = repository.cleanup_finishes[-1]
    assert finish["clear_input"] is True
    assert finish["clear_checkpoint"] is False
    assert finish["clear_result"] is False
    assert finish["purge"] is False


def test_rollback_is_scoped_to_new_objects() -> None:
    sql = ROLLBACK.read_text(encoding="utf-8").lower()
    assert "drop table if exists public.viral_analysis_jobs" in sql
    assert "drop table if exists public.profiles" not in sql
    assert "delete from" not in sql


def test_two_workers_only_one_claims() -> None:
    repository = FakeRepository(_job())
    first = repository.claim(worker_owner="one", lease_seconds=60)
    second = repository.claim(worker_owner="two", lease_seconds=60)
    assert first is not None
    assert second is None


def test_stage_success_persists_checkpoint_and_continues() -> None:
    repository = FakeRepository(_job())
    executor = ScriptedExecutor(
        [
            StageResult("final_validating", {"asr": {"transcript": "ok"}, "analysis": {"rewrites": [{"script": "稿"}]}}, 97),
            StageResult("succeeded", {"analysis": {"rewrites": [{"script": "稿"}]}}, 100, result={"rewrites": [{"script": "稿"}]}),
        ]
    )
    worker = ViralJobWorker(repository, executor, worker_owner="one", heartbeat_seconds=99)
    assert run(worker)
    assert repository.job["status"] == "succeeded"
    assert len(repository.finishes) == 2


def test_asr_checkpoint_resume_does_not_call_previous_stages() -> None:
    checkpoint = {"asr": {"transcript": "saved"}, "normalization": {"transcript": "saved"}}
    repository = FakeRepository(_job(stage="a_primary_generation", checkpoint=checkpoint))
    executor = ScriptedExecutor([StageResult("succeeded", checkpoint, 100, result={"rewrites": [{"script": "稿"}]})])
    assert run(ViralJobWorker(repository, executor, worker_owner="one", heartbeat_seconds=99))
    assert executor.calls[0]["stage"] == "a_primary_generation"
    assert executor.calls[0]["checkpoint"]["asr"]["transcript"] == "saved"


def test_production_executor_skips_asr_when_durable_checkpoint_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def forbidden_asr(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise AssertionError("ASR must not run after its checkpoint exists")

    class MinimalRepository:
        supabase = object()

    monkeypatch.setattr(worker_module, "transcribe_audio", forbidden_asr)
    executor = ProductionViralStageExecutor(MinimalRepository())  # type: ignore[arg-type]
    job = _job(
        status="running",
        stage="transcribing",
        checkpoint={"asr": {"transcript": "saved", "segments": []}},
    )
    result = asyncio.run(executor.execute(job))
    assert result.next_stage == "transcript_correcting"


def test_derived_audio_upload_is_idempotent_but_user_upload_is_not() -> None:
    worker_source = (ROOT / "apps" / "api" / "app" / "services" / "viral_job_worker.py").read_text(encoding="utf-8")
    api_source = (ROOT / "apps" / "api" / "app" / "api" / "viral.py").read_text(encoding="utf-8")
    assert 'content_type="audio/wav",\n                    upsert=True,' in worker_source
    upload_call = api_source.split("repository.upload_file,", 1)[1].split(")", 1)[0]
    assert "upsert=True" not in upload_call


def test_fact_review_checkpoint_can_resume_targeted_repair() -> None:
    checkpoint = {"fact_review": {"reviewed_script": "safe"}}
    repository = FakeRepository(_job(stage="a_targeted_repair", checkpoint=checkpoint))
    executor = ScriptedExecutor([StageResult("succeeded", checkpoint, 100, result={"rewrites": [{"script": "稿"}]})])
    assert run(ViralJobWorker(repository, executor, worker_owner="one", heartbeat_seconds=99))
    assert executor.calls[0]["stage"] == "a_targeted_repair"
    assert executor.calls[0]["checkpoint"]["fact_review"]["reviewed_script"] == "safe"


def test_successful_model_response_is_persisted_and_replayed_without_second_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    persisted: list[tuple[str, str]] = []

    async def fake_chat(self: LLMProvider, **kwargs: Any) -> dict[str, Any]:
        del self, kwargs
        nonlocal calls
        calls += 1
        return {"review": {"audited_script": "safe"}}

    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(LLMProvider, "_chat_json", fake_chat)
    cache: dict[str, dict[str, Any]] = {}
    token = bind_llm_replay_context(
        LLMReplayContext(cache=cache, persist=lambda key, stage: persisted.append((key, stage)))
    )

    async def invoke_twice() -> tuple[dict[str, Any], dict[str, Any]]:
        provider = LLMProvider()
        kwargs = {
            "system": "review",
            "payload": {"current_rewrites": [{"index": 0}]},
            "attempt_label": "fact_review_call_1",
        }
        return await provider.generate_json(**kwargs), await provider.generate_json(**kwargs)

    try:
        first, second = asyncio.run(invoke_twice())
    finally:
        reset_llm_replay_context(token)
    assert first == second
    assert calls == 1
    assert len(cache) == 1
    assert [stage for _, stage in persisted] == ["a_fact_review"]


def test_fact_review_crash_replays_completed_calls_and_only_invokes_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_calls: list[str] = []

    async def fake_chat(self: LLMProvider, **kwargs: Any) -> dict[str, Any]:
        del self
        provider_calls.append(str(kwargs["attempt_label"]))
        return {"value": kwargs["attempt_label"]}

    class CheckpointRepository:
        supabase = object()

        def __init__(self) -> None:
            self.saved: dict[str, Any] = {}
            self.stages: list[str] = []

        def checkpoint_progress(self, **kwargs: Any) -> dict[str, Any]:
            job = kwargs["job"]
            self.saved = deepcopy(kwargs["checkpoint"])
            self.stages.append(kwargs["stage"])
            return {
                "accepted": True,
                "new_revision": int(job["revision"]) + 1,
                "observed_status": "running",
            }

    first_run = True

    async def fake_analyzer(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        provider = LLMProvider()
        await provider.generate_json(
            system="primary", payload={"variant_task": {"index": 0}}, attempt_label="variant_0_attempt_1"
        )
        await provider.generate_json(
            system="review", payload={"current_rewrites": [{"index": 0}]}, attempt_label="fact_review_call_2"
        )
        if first_run:
            raise TimeoutError("worker crashed after fact review")
        await provider.generate_json(
            system="repair", payload={"primary_convergence": True}, attempt_label="primary_convergence_0_1_call_3"
        )
        return {"rewrites": [{"script": "安全稿"}], "diagnostics": {}}

    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(LLMProvider, "_chat_json", fake_chat)
    monkeypatch.setattr(worker_module, "analyze_viral_script", fake_analyzer)
    repository = CheckpointRepository()
    executor = ProductionViralStageExecutor(repository)  # type: ignore[arg-type]
    executor.configure_checkpointing(worker_owner="worker-a", lease_seconds=60)
    base_checkpoint = {
        "email": "preview@example.invalid",
        "industry": "knowledge",
        "language": "zh",
        "rewrite_length": "match_source",
        "normalization": {"transcript": "来源转写", "sentences": []},
        "asr": {"coverage_seconds": 170},
    }
    first_job = _job(status="running", stage="a_primary_generation", revision=1, checkpoint=base_checkpoint)
    with pytest.raises(TimeoutError):
        asyncio.run(executor.execute(first_job))
    assert provider_calls == ["variant_0_attempt_1", "fact_review_call_2"]
    assert repository.stages[-1] == "a_fact_review"

    first_run = False
    resumed_job = _job(
        status="running",
        stage="a_fact_review",
        revision=first_job["revision"],
        checkpoint=repository.saved,
    )
    result = asyncio.run(executor.execute(resumed_job))
    assert result.next_stage == "final_validating"
    assert provider_calls == [
        "variant_0_attempt_1",
        "fact_review_call_2",
        "primary_convergence_0_1_call_3",
    ]
    assert repository.stages[-1] == "a_targeted_repair"


def test_network_failure_has_limited_retry_and_backoff() -> None:
    repository = FakeRepository(_job(attempt=0))
    executor = ScriptedExecutor([TimeoutError("network")])
    assert run(ViralJobWorker(repository, executor, worker_owner="one", heartbeat_seconds=99))
    finish = repository.finishes[-1]
    assert finish["next_status"] == "retry_wait"
    assert finish["retryable"] is True
    assert finish["next_retry_at"]


def test_quality_failure_does_not_retry_forever() -> None:
    repository = FakeRepository(_job())
    executor = ScriptedExecutor([StageFailure(category="quality", code="quality_failed", message="bad", retryable=False)])
    assert run(ViralJobWorker(repository, executor, worker_owner="one", heartbeat_seconds=99))
    assert repository.job["status"] == "failed"
    assert repository.finishes[-1]["retryable"] is False


def test_retry_stops_at_max_attempts() -> None:
    repository = FakeRepository(_job(attempt=2, max_attempts=3))
    executor = ScriptedExecutor([TimeoutError("network")])
    assert run(ViralJobWorker(repository, executor, worker_owner="one", heartbeat_seconds=99))
    assert repository.job["status"] == "failed"


def test_cancel_requested_reaches_cancelled_without_executor_call() -> None:
    job = _job(status="pending")
    repository = FakeRepository(job)
    claimed = repository.claim(worker_owner="one", lease_seconds=60)
    assert claimed
    claimed["status"] = "cancel_requested"
    repository.job["status"] = "cancel_requested"
    executor = ScriptedExecutor([])
    asyncio.run(ViralJobWorker(repository, executor, worker_owner="one")._run_claimed(claimed))
    assert repository.job["status"] == "cancelled"
    assert executor.calls == []


def test_late_worker_cannot_overwrite_terminal_result() -> None:
    repository = FakeRepository(_job(status="succeeded", revision=9, lease_owner=None))
    accepted = repository.finish_stage(
        job=_job(status="running", revision=2, lease_owner="old"),
        worker_owner="old",
        outcome="failed",
        next_status="failed",
        next_stage="failed",
        progress=20,
        checkpoint={},
    )
    assert accepted is False
    assert repository.job["status"] == "succeeded"


def test_stage_deadline_remains_180_seconds() -> None:
    assert settings.viral_job_stage_timeout_seconds == 180


def test_feature_flag_defaults_off_for_rollback() -> None:
    assert settings.viral_async_jobs_enabled is False


def test_feature_disabled_signal_is_explicit_and_machine_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "viral_async_jobs_enabled", False)
    with pytest.raises(viral_api.HTTPException) as captured:
        viral_api._require_async_jobs()
    assert captured.value.status_code == 404
    assert captured.value.detail == {
        "code": "viral_async_jobs_disabled",
        "message": "Async viral jobs are disabled.",
    }


def test_auth_failure_precedes_feature_disabled_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "viral_async_jobs_enabled", False)

    def reject_auth(_supabase: object, _token: str) -> dict[str, str]:
        raise viral_api.HTTPException(status_code=401, detail="invalid auth")

    monkeypatch.setattr(viral_api, "get_authenticated_user", reject_auth)
    with pytest.raises(viral_api.HTTPException) as captured:
        asyncio.run(viral_api.list_viral_jobs(limit=20, token="invalid", supabase=object()))  # type: ignore[arg-type]
    assert captured.value.status_code == 401
    assert captured.value.detail == "invalid auth"


def test_frontend_storage_key_is_scoped_by_authenticated_user() -> None:
    source = WEB_CLIENT.read_text(encoding="utf-8")
    assert "viral-analysis-job:${supabaseProjectRef}:${user.id}" in source
    assert "getViralJob(jobId, accessToken)" in source


def test_frontend_bundle_sources_never_reference_service_role_key() -> None:
    source = WEB_CLIENT.read_text(encoding="utf-8") + WEB_API.read_text(encoding="utf-8")
    assert "SUPABASE_SERVICE_ROLE_KEY" not in source
    assert "sb_secret_" not in source


def test_new_preview_files_do_not_embed_production_ref() -> None:
    forbidden = "povfvhdn" + "rpytxbbyndit"
    for path in (MIGRATION, ROLLBACK, WEB_CLIENT, WEB_API):
        assert forbidden not in path.read_text(encoding="utf-8")


def test_api_status_contract_does_not_expose_internal_fields() -> None:
    api_source = (ROOT / "apps" / "api" / "app" / "api" / "viral.py").read_text(encoding="utf-8")
    response_block = api_source.split("def _safe_job_response", 1)[1].split("def _is_pipeline_tester", 1)[0]
    for forbidden in ("checkpoint", "input_object_path", "lease_owner", "provider_raw_error"):
        assert forbidden not in response_block


def test_worker_stage_progress_is_monotonic() -> None:
    values = [STAGE_PROGRESS[name] for name in (
        "media_received", "media_extracting", "asr_loading", "transcribing",
        "transcript_correcting", "asr_normalizing", "a_primary_generation",
        "a_fact_review", "a_targeted_repair", "optional_variants",
        "final_validating", "succeeded",
    )]
    assert values == sorted(values)
