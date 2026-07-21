from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from supabase import Client

from app.core.config import settings
from app.services.storage import upload_public_bytes
from app.services.subtitles import (
    MediaDurationError,
    MediaInfo,
    SubtitleBurnError,
    build_subtitle_segments,
    burn_subtitles_to_video,
    normalize_script_text,
    probe_media_info,
    probe_video_duration,
    validate_stream_duration_alignment,
    write_ass_file,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AvatarVideoResult:
    result_url: str
    subtitle_status: str


async def generate_avatar_video_with_musetalk(
    supabase: Client,
    *,
    video_url: str,
    audio_url: str,
    task_id: str,
    script_text: str | None = None,
) -> AvatarVideoResult:
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
        raise HTTPException(status_code=504, detail="MuseTalk generation timeout") from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"MuseTalk service request failed: {error}") from error

    output_media = _inspect_musetalk_output(video_response.content, task_id=task_id)
    video_content, subtitle_status = _with_optional_subtitles(
        video_response.content,
        task_id=task_id,
        script_text=script_text,
    )
    if subtitle_status != "burned":
        _log_final_media(task_id, output_media, subtitle_status)

    result_url = upload_public_bytes(
        supabase,
        settings.supabase_video_bucket,
        video_content,
        f"avatar-results/{task_id}",
        ".mp4",
        "video/mp4",
    )
    logger.info(
        "MuseTalk upload completed task_id=%s result_url=%s bytes=%s subtitle_status=%s",
        task_id,
        result_url,
        len(video_content),
        subtitle_status,
    )
    return AvatarVideoResult(result_url=result_url, subtitle_status=subtitle_status)


def _with_optional_subtitles(video_content: bytes, *, task_id: str, script_text: str | None) -> tuple[bytes, str]:
    clean_text = normalize_script_text(script_text)
    if not settings.avatar_subtitles_enabled:
        logger.info("subtitle_burn_disabled task_id=%s", task_id)
        return video_content, "disabled"
    if not clean_text:
        logger.info("subtitle_burn_skipped_empty_script task_id=%s", task_id)
        return video_content, "disabled"

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "musetalk-output.mp4"
            ass_path = tmp_path / "subtitle.ass"
            output_path = tmp_path / "captioned-output.mp4"

            input_path.write_bytes(video_content)
            duration = probe_video_duration(input_path, settings.ffmpeg_path)
            segments = build_subtitle_segments(clean_text, duration)
            if not segments:
                logger.info("subtitle_burn_skipped_no_segments task_id=%s", task_id)
                return video_content, "disabled"
            write_ass_file(segments, ass_path)
            burn_subtitles_to_video(input_path, ass_path, output_path, settings.ffmpeg_path)
            final_media = probe_media_info(output_path, settings.ffmpeg_path)
            _log_final_media(task_id, final_media, "burned")
            captioned = output_path.read_bytes()
            if not _looks_like_mp4(captioned):
                raise HTTPException(status_code=500, detail="Captioned output is not a valid MP4 file")
            logger.info(
                "subtitle_burn_success task_id=%s duration=%s segments=%s output_size=%s",
                task_id,
                duration,
                len(segments),
                len(captioned),
            )
            return captioned, "burned"
    except MediaDurationError as error:
        logger.error("avatar_duration_guard_failed task_id=%s detail=%s", task_id, error.detail)
        raise HTTPException(status_code=502, detail=error.detail) from error
    except SubtitleBurnError as error:
        logger.warning(
            "subtitle_burn_failed_diagnostic task_id=%s diagnostics=%s",
            task_id,
            error.diagnostics,
        )
        logger.warning("subtitle_burn_failed_fallback_original task_id=%s error=%s", task_id, str(error)[:300])
        if settings.avatar_subtitle_fallback_on_error:
            return video_content, "fallback_original"
        raise
    except Exception as error:
        logger.warning("subtitle_burn_failed_fallback_original task_id=%s error=%s", task_id, str(error)[:800])
        if settings.avatar_subtitle_fallback_on_error:
            return video_content, "fallback_original"
        raise


def _inspect_musetalk_output(video_content: bytes, *, task_id: str) -> MediaInfo:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "musetalk-output.mp4"
            input_path.write_bytes(video_content)
            media = probe_media_info(input_path, settings.ffmpeg_path)
            validate_stream_duration_alignment(media, stage="musetalk_output")
    except MediaDurationError as error:
        logger.error("avatar_duration_guard_failed task_id=%s detail=%s", task_id, error.detail)
        raise HTTPException(status_code=502, detail=error.detail) from error
    logger.info(
        "MuseTalk output media task_id=%s video_duration=%.6f video_frames=%s video_fps=%.6f audio_duration=%s",
        task_id,
        media.video_duration,
        media.video_frames,
        media.fps,
        f"{media.audio_duration:.6f}" if media.audio_duration is not None else "missing",
    )
    return media


def _log_final_media(task_id: str, media: MediaInfo, subtitle_status: str) -> None:
    logger.info(
        "Avatar final media task_id=%s subtitle_status=%s video_duration=%.6f video_frames=%s "
        "video_fps=%.6f audio_duration=%s",
        task_id,
        subtitle_status,
        media.video_duration,
        media.video_frames,
        media.fps,
        f"{media.audio_duration:.6f}" if media.audio_duration is not None else "missing",
    )


async def check_musetalk_health() -> dict[str, Any]:
    base_url = settings.musetalk_api_base_url.strip().rstrip("/")
    if not base_url:
        return {"status": "missing_config"}
    configured_host = urlparse(base_url).hostname or ""
    headers = {}
    if settings.musetalk_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.musetalk_api_key.strip()}"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(f"{base_url}/health", headers=headers)
            data = _parse_json(response)
            content_type = response.headers.get("content-type", "")
            if not response.is_success:
                return {
                    "status": "unhealthy",
                    "status_code": response.status_code,
                    "message": "MuseTalk health check returned a non-2xx response.",
                    "content_type": content_type,
                    "preview": _text_preview(response),
                    "configured_host": configured_host,
                }
            if not data:
                return {
                    "status": "unhealthy",
                    "status_code": response.status_code,
                    "message": "MuseTalk health check returned non-JSON or empty response.",
                    "content_type": content_type,
                    "preview": _text_preview(response),
                    "configured_host": configured_host,
                }
            health_status = str(data.get("status") or "").lower()
            if health_status not in {"ok", "ready", "healthy"}:
                return {
                    **data,
                    "status": health_status or "unhealthy",
                    "status_code": response.status_code,
                    "configured_host": configured_host,
                }
            return {**data, "status": "ok", "status_code": response.status_code, "configured_host": configured_host}
    except httpx.TimeoutException:
        return {
            "status": "error",
            "message": "MuseTalk health check timeout",
            "configured_host": configured_host,
        }
    except Exception as error:
        return {"status": "error", "message": str(error), "configured_host": configured_host}


def _parse_json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {"data": data}
    except ValueError:
        return {}


def _text_preview(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "")
    if "text" not in content_type and "html" not in content_type and "json" not in content_type:
        return ""
    try:
        return response.text[:200]
    except UnicodeDecodeError:
        return ""


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
