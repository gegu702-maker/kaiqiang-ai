from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from supabase import Client

from app.core.config import settings
from app.services.storage import upload_public_bytes

logger = logging.getLogger(__name__)


async def generate_avatar_video_with_musetalk(
    supabase: Client,
    *,
    video_url: str,
    audio_url: str,
    task_id: str,
) -> str:
    base_url = settings.musetalk_api_base_url.strip().rstrip("/")
    if not base_url:
        raise HTTPException(status_code=503, detail="MUSE_TALK_API_BASE_URL missing")

    payload = {"video_url": video_url, "audio_url": audio_url, "task_id": task_id}
    headers = {"Content-Type": "application/json"}
    if settings.musetalk_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.musetalk_api_key.strip()}"

    try:
        async with httpx.AsyncClient(timeout=settings.musetalk_timeout_seconds, follow_redirects=True) as client:
            logger.info("MuseTalk request task_id=%s endpoint=%s/generate video_url=%s audio_url=%s", task_id, base_url, video_url, audio_url)
            response = await client.post(f"{base_url}/generate", json=payload, headers=headers)
            data = _parse_json(response)
            logger.info("MuseTalk response task_id=%s status_code=%s body=%s", task_id, response.status_code, data or response.text[:1000])
            if not response.is_success:
                raise HTTPException(status_code=502, detail=_musetalk_error(data, response.text))

            output_url = _normalize_musetalk_result_url(_extract_video_url(data), base_url)
            logger.info("MuseTalk output task_id=%s output_url=%s", task_id, output_url)
            video_response = await client.get(output_url)
            if not video_response.is_success:
                raise HTTPException(status_code=502, detail=f"MuseTalk output download failed: {video_response.status_code}")
    except HTTPException:
        raise
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail="MuseTalk generation timeout") from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"MuseTalk service request failed: {error}") from error

    result_url = upload_public_bytes(
        supabase,
        settings.supabase_video_bucket,
        video_response.content,
        f"avatar-results/{task_id}",
        ".mp4",
        "video/mp4",
    )
    logger.info("MuseTalk upload completed task_id=%s result_url=%s bytes=%s", task_id, result_url, len(video_response.content))
    return result_url


async def check_musetalk_health() -> dict[str, Any]:
    base_url = settings.musetalk_api_base_url.strip().rstrip("/")
    if not base_url:
        return {"status": "missing_config"}
    headers = {}
    if settings.musetalk_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.musetalk_api_key.strip()}"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(f"{base_url}/health", headers=headers)
            data = _parse_json(response)
            return data if isinstance(data, dict) else {"status": "unknown"}
    except Exception as error:
        return {"status": "error", "message": str(error)}


def _parse_json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {"data": data}
    except ValueError:
        return {}


def _extract_video_url(data: dict[str, Any]) -> str:
    status = str(data.get("status") or "").lower()
    if status and status not in {"completed", "success", "ok"}:
        raise HTTPException(status_code=502, detail=_musetalk_error(data, "MuseTalk generation failed"))
    video_url = data.get("video_url") or data.get("result_url")
    if not video_url:
        raise HTTPException(status_code=502, detail="MuseTalk output video missing")
    return str(video_url)


def _musetalk_error(data: dict[str, Any], raw: str) -> dict[str, Any] | str:
    if data:
        return {
            "message": data.get("detail") or data.get("error") or data.get("message") or "MuseTalk generation failed",
            "status": data.get("status"),
            "error": data.get("error"),
        }
    return raw[:1000] or "MuseTalk generation failed"


def _normalize_musetalk_result_url(output_url: str, base_url: str) -> str:
    parsed_output = urlparse(output_url)
    parsed_base = urlparse(base_url)
    if parsed_output.path.startswith("/results/") and parsed_output.hostname in {parsed_base.hostname, "127.0.0.1", "localhost"}:
        return f"{base_url.rstrip('/')}{parsed_output.path}"
    return output_url
