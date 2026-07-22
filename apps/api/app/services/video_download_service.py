from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.douyin_ytdlp import build_douyin_ytdlp_options, normalize_douyin_web_url

DOWNLOAD_FALLBACK = "该视频暂不支持自动解析，请上传视频继续分析。"


@dataclass
class DownloadedVideo:
    ok: bool
    video_path: Path | None = None
    title: str = ""
    description: str = ""
    duration: int = 0
    thumbnail: str = ""
    webpage_url: str = ""
    fallback_reason: str = ""


def _download_with_ytdlp(url: str, work_dir: Path) -> DownloadedVideo:
    normalized_url = normalize_douyin_web_url(url)
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return DownloadedVideo(ok=False, webpage_url=normalized_url, fallback_reason="服务端未安装 yt-dlp，暂时无法下载视频。")

    work_dir.mkdir(parents=True, exist_ok=True)
    options = build_douyin_ytdlp_options("download")
    options.update(
        {
            "merge_output_format": "mp4",
            "outtmpl": str(work_dir / "%(id)s.%(ext)s"),
            "max_filesize": settings.viral_max_download_mb * 1024 * 1024,
        }
    )
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(normalized_url, download=True)
    except Exception:
        return DownloadedVideo(ok=False, webpage_url=normalized_url, fallback_reason=DOWNLOAD_FALLBACK)

    if not isinstance(info, dict):
        return DownloadedVideo(ok=False, webpage_url=normalized_url, fallback_reason=DOWNLOAD_FALLBACK)

    duration = int(info.get("duration") or 0)
    if duration and duration > settings.viral_max_video_duration_seconds:
        return DownloadedVideo(
            ok=False,
            webpage_url=str(info.get("webpage_url") or normalized_url),
            fallback_reason=f"当前仅支持 {settings.viral_max_video_duration_seconds} 秒以内的视频，请上传较短视频继续分析。",
        )

    video_path = _find_downloaded_file(work_dir, info)
    if not video_path:
        return DownloadedVideo(ok=False, webpage_url=str(info.get("webpage_url") or normalized_url), fallback_reason=DOWNLOAD_FALLBACK)

    max_bytes = settings.viral_max_download_mb * 1024 * 1024
    if video_path.stat().st_size > max_bytes:
        return DownloadedVideo(
            ok=False,
            webpage_url=str(info.get("webpage_url") or normalized_url),
            fallback_reason=f"当前仅支持 {settings.viral_max_download_mb}MB 以内的视频，请上传较小视频继续分析。",
        )

    return DownloadedVideo(
        ok=True,
        video_path=video_path,
        title=str(info.get("title") or ""),
        description=str(info.get("description") or info.get("fulltitle") or ""),
        duration=duration,
        thumbnail=str(info.get("thumbnail") or ""),
        webpage_url=str(info.get("webpage_url") or normalized_url),
    )


def _find_downloaded_file(work_dir: Path, info: dict[str, Any]) -> Path | None:
    requested = info.get("requested_downloads") or []
    for item in requested:
        if isinstance(item, dict):
            filepath = item.get("filepath")
            if filepath and Path(filepath).exists():
                return Path(filepath)

    candidates = [path for path in work_dir.iterdir() if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


async def download_video(url: str, work_dir: Path) -> DownloadedVideo:
    return await asyncio.to_thread(_download_with_ytdlp, url, work_dir)


async def extract_audio(video_path: Path, work_dir: Path) -> Path:
    audio_path = work_dir / "audio.wav"
    command = [
        settings.ffmpeg_path,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(audio_path),
    ]
    try:
        await asyncio.to_thread(
            subprocess.run,
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=min(settings.viral_pipeline_timeout_seconds, 600),
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
        raise RuntimeError(f"音频提取失败：{detail}") from error
    return audio_path


async def probe_media_duration(video_path: Path) -> float:
    """Return container duration without decoding or uploading the media."""
    ffmpeg_name = Path(settings.ffmpeg_path)
    ffprobe_path = str(ffmpeg_name.with_name("ffprobe.exe" if ffmpeg_name.suffix.lower() == ".exe" else "ffprobe"))
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        completed = await asyncio.to_thread(
            subprocess.run,
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(json.loads(completed.stdout)["format"]["duration"])
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"无法读取视频时长：{error}") from error
