from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from supabase import Client

from app.core.config import settings
from app.services.avatar_subtitles import burn_subtitles_into_video_bytes
from app.services.storage import upload_public_bytes

logger = logging.getLogger(__name__)


async def generate_avatar_video_with_musetalk(
    supabase: Client,
    *,
    video_url: str,
    audio_url: str,
    task_id: str,
    subtitle_text: str | None = None,
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
    except HTTPException:
        raise
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail="MuseTalk generation timeout") from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"MuseTalk service request failed: {error}") from error

    return await finalize_avatar_video_from_result_url(
        supabase,
        task_id=task_id,
        result_video_url=output_url,
        subtitle_text=subtitle_text,
    )


async def finalize_avatar_video_from_result_url(
    supabase: Client,
    *,
    task_id: str,
    result_video_url: str,
    subtitle_text: str | None = None,
) -> str:
    try:
        async with httpx.AsyncClient(timeout=settings.musetalk_timeout_seconds, follow_redirects=True) as client:
            logger.info("MuseTalk output download started task_id=%s output_url=%s", task_id, result_video_url)
            video_response = await client.get(result_video_url)
            if not video_response.is_success:
                raise HTTPException(status_code=502, detail=f"MuseTalk output download failed: {video_response.status_code}")
            if not _looks_like_mp4(video_response.content):
                content_type = video_response.headers.get("content-type", "")
                preview = video_response.text[:300] if "text" in content_type or "html" in content_type else ""
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "MuseTalk output is not a valid MP4 file",
                        "content_type": content_type,
                        "bytes": len(video_response.content),
                        "preview": preview,
                    },
                )
    except HTTPException:
        raise
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail="MuseTalk output download timeout") from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"MuseTalk output download failed: {error}") from error

    final_video_bytes = video_response.content
    if (subtitle_text or "").strip():
        logger.info("MuseTalk subtitle burn started task_id=%s subtitle_length=%s", task_id, len(subtitle_text or ""))
        final_video_bytes = burn_subtitles_into_video_bytes(video_response.content, subtitle_text or "")
        logger.info("MuseTalk subtitle burn completed task_id=%s bytes=%s", task_id, len(final_video_bytes))

    result_url = upload_public_bytes(
        supabase,
        settings.supabase_video_bucket,
        final_video_bytes,
        f"avatar-results/{task_id}",
        ".mp4",
        "video/mp4",
    )
    logger.info("MuseTalk upload completed task_id=%s result_url=%s bytes=%s", task_id, result_url, len(final_video_bytes))
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
            if data:
                return data
            if response.is_success:
                body = response.text.strip()
                return {"status": body or "ok"}
            return {"status": "error", "status_code": response.status_code, "message": response.text[:300]}
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


def _looks_like_mp4(content: bytes) -> bool:
    if len(content) < 1024:
        return False
    return b"ftyp" in content[:32]
