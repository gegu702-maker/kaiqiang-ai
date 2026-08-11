from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import quote

import httpx
from supabase import Client

from app.core.config import settings


SAFE_JOB_COLUMNS = (
    "id,request_id,user_id,file_fingerprint,parameter_version,status,stage,progress,"
    "attempt,retryable,next_retry_at,error_class,error_code,safe_error_message,"
    "stage_started_at,stage_finished_at,stage_elapsed_ms,quality,provenance,result,"
    "created_at,updated_at,completed_at"
)

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
ACTIVE_STATUSES = {"uploading", "pending", "running", "retry_wait", "cancel_requested"}
_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+"
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def sanitize_error_message(value: object) -> str:
    message = str(value or "任务处理失败。")
    message = _SECRET_PATTERN.sub(r"\1=[REDACTED]", message)
    message = re.sub(r"(?:[A-Za-z]:\\|/tmp/|/var/)[^\s]+", "[INTERNAL_PATH]", message)
    return message[:2000]


def parameter_version(*, params_hash: str, pipeline_version: str) -> str:
    return hashlib.sha256(f"{params_hash}:{pipeline_version}".encode()).hexdigest()


class ViralJobRepository:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    def create_or_reuse(
        self,
        *,
        user_id: str,
        request_id: str,
        fingerprint: str,
        parameter_version_value: str,
        params_hash: str,
        pipeline_version: str,
    ) -> dict[str, Any]:
        result = self.supabase.rpc(
            "create_or_reuse_viral_analysis_job",
            {
                "p_user_id": user_id,
                "p_request_id": request_id,
                "p_file_fingerprint": fingerprint,
                "p_parameter_version": parameter_version_value,
                "p_analysis_params_hash": params_hash,
                "p_pipeline_version": pipeline_version,
            },
        ).execute()
        if not result.data:
            raise RuntimeError("Async job creation returned no row.")
        return dict(result.data[0])

    def mark_uploaded(
        self,
        *,
        job_id: str,
        user_id: str,
        bucket: str,
        object_path: str,
        checkpoint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = (
            self.supabase.table("viral_analysis_jobs")
            .update(
                {
                    "status": "pending",
                    "stage": "media_received",
                    "progress": 5,
                    "input_bucket": bucket,
                    "input_object_path": object_path,
                    **({"checkpoint": checkpoint} if checkpoint is not None else {}),
                    "checkpoint_stage": "media_received",
                    "input_expires_at": None,
                    "purge_after": None,
                    "revision": 1,
                }
            )
            .eq("id", job_id)
            .eq("user_id", user_id)
            .eq("status", "uploading")
            .eq("revision", 0)
            .execute()
        )
        if not result.data:
            raise RuntimeError("Upload completion lost its revision CAS.")
        return dict(result.data[0])

    def prepare_upload(
        self,
        *,
        job_id: str,
        user_id: str,
        bucket: str,
        object_path: str,
        checkpoint: dict[str, Any] | None = None,
    ) -> None:
        values: dict[str, Any] = {"input_bucket": bucket, "input_object_path": object_path}
        if checkpoint is not None:
            values.update({"checkpoint": checkpoint, "checkpoint_stage": "uploading"})
        result = (
            self.supabase.table("viral_analysis_jobs")
            .update(values)
            .eq("id", job_id)
            .eq("user_id", user_id)
            .eq("status", "uploading")
            .eq("revision", 0)
            .execute()
        )
        if not result.data:
            raise RuntimeError("Upload preparation lost its revision CAS.")

    def fail_upload(self, *, job_id: str, user_id: str, code: str, message: str) -> None:
        (
            self.supabase.table("viral_analysis_jobs")
            .update(
                {
                    "status": "failed",
                    "stage": "media_received",
                    "progress": 0,
                    "error_class": "upload",
                    "error_code": code,
                    "safe_error_message": sanitize_error_message(message),
                    "retryable": True,
                    "completed_at": utc_now_iso(),
                    "revision": 1,
                }
            )
            .eq("id", job_id)
            .eq("user_id", user_id)
            .eq("status", "uploading")
            .eq("revision", 0)
            .execute()
        )

    def get_for_user(self, *, job_id: str, user_id: str) -> dict[str, Any] | None:
        result = (
            self.supabase.table("viral_analysis_jobs")
            .select(SAFE_JOB_COLUMNS)
            .eq("id", job_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return dict(result.data[0]) if result.data else None

    def list_for_user(self, *, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        result = (
            self.supabase.table("viral_analysis_jobs")
            .select(SAFE_JOB_COLUMNS)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(max(1, min(limit, 50)))
            .execute()
        )
        return [dict(item) for item in result.data or []]

    def get_internal(self, job_id: str) -> dict[str, Any] | None:
        result = (
            self.supabase.table("viral_analysis_jobs")
            .select("*")
            .eq("id", job_id)
            .limit(1)
            .execute()
        )
        return dict(result.data[0]) if result.data else None

    def get_internal_for_user(self, *, job_id: str, user_id: str) -> dict[str, Any] | None:
        result = (
            self.supabase.table("viral_analysis_jobs")
            .select("*")
            .eq("id", job_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return dict(result.data[0]) if result.data else None

    def request_cancel(self, *, job_id: str, user_id: str) -> dict[str, Any] | None:
        result = self.supabase.rpc(
            "request_cancel_viral_analysis_job",
            {"p_job_id": job_id, "p_user_id": user_id},
        ).execute()
        if not result.data:
            return None
        return self.get_for_user(job_id=job_id, user_id=user_id)

    def claim(self, *, worker_owner: str, lease_seconds: int) -> dict[str, Any] | None:
        result = self.supabase.rpc(
            "claim_viral_analysis_job",
            {"p_worker_owner": worker_owner, "p_lease_seconds": lease_seconds},
        ).execute()
        return dict(result.data[0]) if result.data else None

    def heartbeat(
        self,
        *,
        job_id: str,
        worker_owner: str,
        revision: int,
        lease_seconds: int,
    ) -> dict[str, Any]:
        result = self.supabase.rpc(
            "heartbeat_viral_analysis_job",
            {
                "p_job_id": job_id,
                "p_worker_owner": worker_owner,
                "p_expected_revision": revision,
                "p_lease_seconds": lease_seconds,
            },
        ).execute()
        row = dict(result.data[0]) if result.data else {}
        if not row.get("accepted"):
            raise RuntimeError("Job lease or revision was lost.")
        return row

    def checkpoint_progress(
        self,
        *,
        job: dict[str, Any],
        worker_owner: str,
        stage: str,
        checkpoint: dict[str, Any],
        lease_seconds: int,
    ) -> dict[str, Any]:
        result = self.supabase.rpc(
            "checkpoint_viral_analysis_job",
            {
                "p_job_id": job["id"],
                "p_worker_owner": worker_owner,
                "p_expected_revision": int(job["revision"]),
                "p_stage": stage,
                "p_checkpoint": checkpoint,
                "p_lease_seconds": lease_seconds,
            },
        ).execute()
        row = dict(result.data[0]) if result.data else {}
        if not row.get("accepted"):
            raise RuntimeError("Job checkpoint lost its lease or revision CAS.")
        return row

    def finish_stage(
        self,
        *,
        job: dict[str, Any],
        worker_owner: str,
        outcome: str,
        next_status: str,
        next_stage: str,
        progress: int,
        checkpoint: dict[str, Any] | None,
        result: dict[str, Any] | None = None,
        quality: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        error_class: str | None = None,
        error_code: str | None = None,
        safe_error_message: str | None = None,
        retryable: bool = False,
        next_retry_at: str | None = None,
        elapsed_ms: int = 0,
    ) -> bool:
        response = self.supabase.rpc(
            "finish_viral_analysis_stage",
            {
                "p_job_id": job["id"],
                "p_worker_owner": worker_owner,
                "p_expected_revision": int(job["revision"]),
                "p_outcome": outcome,
                "p_next_status": next_status,
                "p_next_stage": next_stage,
                "p_progress": progress,
                "p_input_version": str(job.get("pipeline_version") or "unknown"),
                "p_output_version": str(job.get("pipeline_version") or "unknown"),
                "p_checkpoint": checkpoint,
                "p_checkpoint_object_path": None,
                "p_output_sha256": None,
                "p_result": result,
                "p_quality": quality,
                "p_provenance": provenance,
                "p_error_class": error_class,
                "p_error_code": error_code,
                "p_safe_error_message": sanitize_error_message(safe_error_message),
                "p_retryable": retryable,
                "p_next_retry_at": next_retry_at,
                "p_elapsed_ms": elapsed_ms,
            },
        ).execute()
        return bool(response.data and response.data[0])

    def claim_cleanup(self, *, worker_owner: str, lease_seconds: int = 120) -> dict[str, Any] | None:
        result = self.supabase.rpc(
            "claim_viral_analysis_cleanup",
            {"p_worker_owner": worker_owner, "p_lease_seconds": lease_seconds},
        ).execute()
        return dict(result.data[0]) if result.data else None

    def finish_cleanup(
        self,
        *,
        job: dict[str, Any],
        worker_owner: str,
        clear_input: bool,
        clear_checkpoint: bool,
        clear_result: bool,
        purge: bool,
        success: bool,
    ) -> bool:
        response = self.supabase.rpc(
            "finish_viral_analysis_cleanup",
            {
                "p_job_id": job["id"],
                "p_worker_owner": worker_owner,
                "p_expected_revision": int(job["revision"]),
                "p_clear_input": clear_input,
                "p_clear_checkpoint": clear_checkpoint,
                "p_clear_result": clear_result,
                "p_purge": purge,
                "p_success": success,
            },
        ).execute()
        return bool(response.data and response.data[0])

    def remove_objects(self, *, bucket: str, object_paths: list[str]) -> None:
        paths = sorted({path for path in object_paths if path})
        if not paths:
            return
        url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{quote(bucket, safe='')}"
        with httpx.Client(timeout=30.0) as client:
            response = client.request(
                "DELETE",
                url,
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "content-type": "application/json",
                },
                json={"prefixes": paths},
            )
        if response.status_code not in {200, 204}:
            raise RuntimeError(f"Artifact cleanup failed with HTTP {response.status_code}.")

    def upload_file(
        self,
        *,
        bucket: str,
        object_path: str,
        source: BinaryIO,
        content_type: str,
        upsert: bool = False,
    ) -> None:
        encoded = "/".join(quote(part, safe="") for part in object_path.split("/"))
        url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{quote(bucket, safe='')}/{encoded}"
        headers = {
            "apikey": settings.supabase_service_role_key,
            "content-type": content_type or "application/octet-stream",
            "x-upsert": "true" if upsert else "false",
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, content=source)
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"Artifact upload failed with HTTP {response.status_code}.")

    def download_file(self, *, bucket: str, object_path: str, destination: Path) -> None:
        encoded = "/".join(quote(part, safe="") for part in object_path.split("/"))
        url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/authenticated/{quote(bucket, safe='')}/{encoded}"
        with httpx.stream(
            "GET",
            url,
            headers={"apikey": settings.supabase_service_role_key},
            timeout=60.0,
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(f"Artifact download failed with HTTP {response.status_code}.")
            with destination.open("wb") as output:
                for chunk in response.iter_bytes():
                    output.write(chunk)
