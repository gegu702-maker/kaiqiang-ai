from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.supabase import get_supabase

logger = logging.getLogger(__name__)

StageCallback = Callable[[str], None]


async def start_instance() -> dict[str, Any]:
    _require_autodl_config()
    if _using_legacy_instance_api():
        return await _normal_instance_request(
            "power_on",
            {
                "instance_uuid": settings.autodl_instance_id.strip(),
                "payload": "gpu",
            },
        )

    payload = _instance_payload()
    payload["payload"] = "gpu"
    payload["start_command"] = "bash /root/autodl-tmp/start_musetalk.sh"
    return await _autodl_request("POST", "/api/v1/dev/instance/pro/power_on", json=payload)


async def stop_instance() -> dict[str, Any]:
    _require_autodl_config()
    if _using_legacy_instance_api():
        return await _normal_instance_request("power_off", _instance_payload())
    return await _autodl_request("POST", "/api/v1/dev/instance/pro/power_off", json=_instance_payload())


async def get_instance_status() -> dict[str, Any]:
    _require_autodl_config()
    if _using_legacy_instance_api():
        return await _normal_instance_request("status", _instance_payload())
    return await _autodl_request("GET", "/api/v1/dev/instance/pro/status", json=_instance_payload())


async def ensure_gpu_ready(stage_callback: StageCallback | None = None) -> dict[str, Any]:
    if await _musetalk_health_ok():
        return {"status": "ready", "source": "health"}

    base_url = settings.musetalk_api_base_url.strip()
    if not base_url:
        raise HTTPException(status_code=503, detail="MUSE_TALK_API_BASE_URL missing")

    if not settings.autodl_auto_start_enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "MuseTalk is not ready. Please manually start AutoDL / MuseTalk and retry.",
                "message_zh": "MuseTalk 服务未就绪，请先手动启动 AutoDL / MuseTalk 后重试。",
                "code": "musetalk_not_ready_manual_start_required",
            },
        )

    _require_autodl_config()
    _set_stage(stage_callback, "gpu_starting")
    await start_instance()

    deadline = asyncio.get_running_loop().time() + settings.autodl_start_timeout_seconds
    model_stage_sent = False
    last_status: dict[str, Any] = {}

    while asyncio.get_running_loop().time() < deadline:
        if await _musetalk_health_ok():
            return {"status": "ready", "source": "autodl"}

        if not model_stage_sent:
            _set_stage(stage_callback, "model_loading")
            model_stage_sent = True

        try:
            last_status = await get_instance_status()
        except Exception as error:
            logger.info("AutoDL status check failed while waiting for MuseTalk: %s", error)

        await asyncio.sleep(10)

    raise HTTPException(
        status_code=504,
        detail={
            "message": "AutoDL GPU started but MuseTalk health check timed out",
            "last_autodl_status": last_status,
        },
    )


async def shutdown_if_idle() -> dict[str, Any]:
    if not _autodl_configured() or not settings.musetalk_api_base_url.strip():
        return {"status": "skipped", "reason": "missing_config"}

    idle_minutes = max(settings.gpu_idle_shutdown_minutes, 1)
    supabase = get_supabase()

    active = supabase.table("avatar_tasks").select("id").in_("status", ["queued", "running"]).limit(1).execute()
    if active.data:
        return {"status": "busy", "active_task_id": active.data[0].get("id")}

    latest = (
        supabase.table("avatar_tasks")
        .select("id,last_gpu_used_at,created_at")
        .eq("status", "completed")
        .order("last_gpu_used_at", desc=True)
        .limit(1)
        .execute()
    )
    if not latest.data:
        return {"status": "idle", "reason": "no_completed_avatar_tasks"}

    last_task = latest.data[0]
    raw_used_at = last_task.get("last_gpu_used_at") or last_task.get("created_at")
    used_at = _parse_datetime(raw_used_at)
    if not used_at:
        return {"status": "idle", "reason": "last_gpu_used_at_missing"}

    idle_for = datetime.now(timezone.utc) - used_at
    if idle_for < timedelta(minutes=idle_minutes):
        return {
            "status": "idle_waiting",
            "idle_seconds": int(idle_for.total_seconds()),
            "shutdown_after_seconds": idle_minutes * 60,
        }

    try:
        instance_status = await get_instance_status()
    except Exception as error:
        logger.info("AutoDL status check before idle shutdown failed: %s", error)
        instance_status = {}

    status_text = _extract_instance_status(instance_status)
    if status_text and status_text in {"stopped", "shutdown", "closed", "off"}:
        return {"status": "already_stopped", "instance_status": instance_status}

    stop_result = await stop_instance()
    return {
        "status": "shutdown_requested",
        "idle_seconds": int(idle_for.total_seconds()),
        "instance_status": instance_status,
        "stop_result": stop_result,
    }


async def autodl_idle_shutdown_loop() -> None:
    while True:
        try:
            result = await shutdown_if_idle()
            if result.get("status") == "shutdown_requested":
                logger.info("AutoDL idle shutdown requested: %s", result)
        except Exception:
            logger.exception("AutoDL idle shutdown check failed")
        await asyncio.sleep(60)


async def _autodl_request(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_url = settings.autodl_api_base_url.strip().rstrip("/") or "https://api.autodl.com"
    headers = {
        "Authorization": settings.autodl_api_token.strip(),
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.request(method, f"{base_url}{path}", headers=headers, json=json, params=params)
            data = _parse_json(response)
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"AutoDL API request failed: {error}") from error

    if not response.is_success or not _autodl_success(data):
        raise HTTPException(
            status_code=502,
            detail={
                "message": "AutoDL API returned an error",
                "status_code": response.status_code,
                "response": data or response.text[:1000],
                "todo": "If AutoDL changes the OpenAPI payload, adjust autodl_client.py endpoint mapping.",
            },
        )
    return data


async def _normal_instance_request(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    candidates = _normal_instance_candidates(action)
    errors: list[dict[str, Any]] = []
    for method, path in candidates:
        try:
            return await _instance_request(method, path, json=payload)
        except HTTPException as error:
            errors.append(_summarize_autodl_error(path, error.detail))
    logger.warning("AutoDL normal instance %s failed for all endpoint candidates: %s", action, errors)
    raise HTTPException(
        status_code=502,
        detail={
            "message": "AutoDL automatic start failed. Please manually start AutoDL / MuseTalk and retry.",
            "message_zh": "AutoDL 自动启动失败，请先手动启动 AutoDL / MuseTalk 后重试。",
            "code": "autodl_auto_start_failed",
            "action": action,
        },
    )


async def _instance_request(method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
    base_url = settings.autodl_api_base_url.strip().rstrip("/") or "https://api.autodl.com"
    headers = {
        "Authorization": settings.autodl_api_token.strip(),
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.request(method, f"{base_url}{path}", headers=headers, json=json)
            data = _parse_json(response)
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"AutoDL API request failed: {error}") from error

    if not response.is_success or not _autodl_success(data):
        raise HTTPException(
            status_code=502,
            detail={
                "message": "AutoDL API returned an error",
                "status_code": response.status_code,
                "response": data or response.text[:1000],
            },
        )
    return data


async def _musetalk_health_ok() -> bool:
    base_url = settings.musetalk_api_base_url.strip().rstrip("/")
    if not base_url:
        return False
    headers = {}
    if settings.musetalk_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.musetalk_api_key.strip()}"
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            response = await client.get(f"{base_url}/health", headers=headers)
            if not response.is_success:
                return False
            data = _parse_json(response)
            return str(data.get("status", "")).lower() in {"ok", "ready", "healthy"}
    except httpx.HTTPError:
        return False


def _instance_payload() -> dict[str, Any]:
    return {"instance_uuid": settings.autodl_instance_id.strip()}


def _using_legacy_instance_api() -> bool:
    return not settings.autodl_instance_id.strip().startswith("pro-")


def _normal_instance_candidates(action: str) -> list[tuple[str, str]]:
    paths = [
        f"/api/v1/dev/instance/{action}",
        f"/api/v1/instance/{action}",
        f"/api/v1/dev/instances/{action}",
        f"/api/v1/dev/container/{action}",
        f"/api/v1/dev/containers/{action}",
    ]
    if action == "status":
        return [("GET", path) for path in paths] + [("POST", path) for path in paths]
    return [("POST", path) for path in paths]


def _summarize_autodl_error(path: str, detail: object) -> dict[str, Any]:
    if not isinstance(detail, dict):
        return {"path": path, "detail": str(detail)[:300]}
    response = detail.get("response")
    if isinstance(response, dict):
        return {
            "path": path,
            "status_code": detail.get("status_code"),
            "code": response.get("code"),
            "status": response.get("status"),
            "msg": response.get("msg") or response.get("message"),
        }
    return {
        "path": path,
        "status_code": detail.get("status_code"),
        "response": str(response or "")[:160],
    }


def _require_autodl_config() -> None:
    missing = []
    if not settings.autodl_api_token.strip():
        missing.append("AUTODL_API_TOKEN")
    if not settings.autodl_instance_id.strip():
        missing.append("AUTODL_INSTANCE_ID")
    if missing:
        raise HTTPException(status_code=503, detail=f"{', '.join(missing)} missing")


def _autodl_configured() -> bool:
    return bool(settings.autodl_api_token.strip() and settings.autodl_instance_id.strip())


def _parse_json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {"data": data}
    except ValueError:
        return {}


def _autodl_success(data: dict[str, Any]) -> bool:
    if not data:
        return True
    code = str(data.get("code", "")).lower()
    status = str(data.get("status", "")).lower()
    if code in {"success", "200", "0"} or status in {"success", "ok"}:
        return True
    if data.get("success") is True:
        return True
    return not code and not status and "error" not in data


def _extract_instance_status(data: dict[str, Any]) -> str:
    current: Any = data
    for key in ("data", "instance", "status"):
        if isinstance(current, dict) and key in current:
            current = current[key]
    if isinstance(current, dict):
        current = current.get("status") or current.get("instance_status") or current.get("power_status")
    return str(current or "").strip().lower()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _set_stage(callback: StageCallback | None, stage: str) -> None:
    if callback is None:
        return
    try:
        callback(stage)
    except Exception:
        logger.exception("Failed to update avatar task stage to %s", stage)
