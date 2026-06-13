from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

DOUYIN_FALLBACK = "当前抖音链接暂时无法自动解析，请粘贴视频文案或上传视频继续分析。"
URL_RE = re.compile(r"https?://[^\s\"'<>，。；、]+", re.IGNORECASE)


@dataclass
class ResolvedVideoLink:
    ok: bool
    platform: str
    title: str = ""
    description: str = ""
    duration: int = 0
    thumbnail: str = ""
    webpage_url: str = ""
    downloadable: bool = False
    fallback_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "platform": self.platform,
            "title": self.title,
            "description": self.description,
            "duration": self.duration,
            "thumbnail": self.thumbnail,
            "webpage_url": self.webpage_url,
            "downloadable": self.downloadable,
            "fallback_reason": self.fallback_reason,
        }


def extract_first_url(value: str) -> str:
    match = URL_RE.search(value or "")
    if not match:
        return ""
    return match.group(0).rstrip(").,，。]")


def is_douyin_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host == "douyin.com" or host.endswith(".douyin.com") or host.endswith(".iesdouyin.com")


def is_douyin_short_url(url: str) -> bool:
    return urlparse(url).netloc.lower() == "v.douyin.com"


async def expand_short_url(url: str) -> str:
    if not is_douyin_short_url(url):
        return url
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=15, headers=headers) as client:
        response = await client.get(url)
    return str(response.url)


def _fallback(*, platform: str = "douyin", webpage_url: str = "", reason: str = DOUYIN_FALLBACK) -> dict[str, Any]:
    return ResolvedVideoLink(
        ok=False,
        platform=platform,
        webpage_url=webpage_url,
        downloadable=False,
        fallback_reason=reason,
    ).to_dict()


def _metadata_with_ytdlp(url: str) -> dict[str, Any]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return _fallback(webpage_url=url, reason="服务端未安装 yt-dlp，暂时无法自动解析抖音链接，请粘贴视频文案或上传视频继续分析。")

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return _fallback(webpage_url=url)

    if not isinstance(info, dict):
        return _fallback(webpage_url=url)

    formats = info.get("formats") or []
    downloadable = bool(info.get("url") or formats)
    if not downloadable:
        return _fallback(webpage_url=info.get("webpage_url") or url)

    return ResolvedVideoLink(
        ok=True,
        platform="douyin",
        title=str(info.get("title") or ""),
        description=str(info.get("description") or info.get("fulltitle") or ""),
        duration=int(info.get("duration") or 0),
        thumbnail=str(info.get("thumbnail") or ""),
        webpage_url=str(info.get("webpage_url") or url),
        downloadable=True,
        fallback_reason="",
    ).to_dict()


async def resolve_video_link(source_url: str) -> dict[str, Any]:
    extracted_url = extract_first_url(source_url)
    if not extracted_url:
        return _fallback(platform="unknown", reason="未识别到有效链接，请粘贴抖音分享链接或视频原文案。")

    try:
        expanded_url = await expand_short_url(extracted_url)
    except Exception:
        expanded_url = extracted_url

    if not is_douyin_url(expanded_url):
        return _fallback(platform="unknown", webpage_url=expanded_url, reason="当前阶段优先支持抖音链接，请粘贴抖音链接或补充视频文案。")

    return await asyncio.to_thread(_metadata_with_ytdlp, expanded_url)
