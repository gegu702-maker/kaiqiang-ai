from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

DOUYIN_FALLBACK = "当前抖音链接暂时无法自动解析，请粘贴视频文案或上传视频继续分析。"
URL_RE = re.compile(r"https?://[^\s\"'<>，。；、]+", re.IGNORECASE)
FALLBACK_OPTIONS = ["upload_video", "paste_text"]

ERROR_MESSAGES = {
    "metadata_blocked": "平台限制自动读取，请上传视频或粘贴原文案继续分析。",
    "redirect_failed": "短链跳转失败，请复制完整链接重试，或上传视频继续分析。",
    "redirect_timeout": "短链跳转超时，请复制完整链接重试，或上传视频继续分析。",
    "not_downloadable": "该视频暂不支持自动读取，请上传视频或粘贴原文案继续分析。",
    "resolver_timeout": "链接检查超时，请稍后重试，或使用上传/粘贴方式。",
    "non_douyin_url": "请输入抖音 / TikTok / YouTube Shorts 链接，或直接上传视频。",
    "unknown_error": "链接解析失败，请上传视频或粘贴原文案继续分析。",
}


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
    error_code: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "success": self.ok,
            "platform": self.platform,
            "title": self.title,
            "description": self.description,
            "duration": self.duration,
            "thumbnail": self.thumbnail,
            "webpage_url": self.webpage_url,
            "downloadable": self.downloadable,
            "fallback_reason": self.fallback_reason,
            "error_code": self.error_code,
            "message": self.message or self.fallback_reason,
            "fallback_available": not self.ok,
            "fallback_options": [] if self.ok else FALLBACK_OPTIONS,
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


def _fallback(
    *,
    platform: str = "douyin",
    webpage_url: str = "",
    reason: str = DOUYIN_FALLBACK,
    error_code: str = "unknown_error",
) -> dict[str, Any]:
    message = ERROR_MESSAGES.get(error_code, reason)
    return ResolvedVideoLink(
        ok=False,
        platform=platform,
        webpage_url=webpage_url,
        downloadable=False,
        fallback_reason=reason,
        error_code=error_code,
        message=message,
    ).to_dict()


def _classify_metadata_error(error: Exception) -> str:
    text = str(error).lower()
    if "timed out" in text or "timeout" in text or "timedout" in text:
        return "resolver_timeout"
    if "unsupported url" in text or "no video formats" in text:
        return "not_downloadable"
    if "login" in text or "captcha" in text or "forbidden" in text or "403" in text or "verify" in text:
        return "metadata_blocked"
    return "metadata_blocked"


def _metadata_with_ytdlp(url: str) -> dict[str, Any]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return _fallback(
            webpage_url=url,
            reason="服务端未安装 yt-dlp，暂时无法自动解析抖音链接，请粘贴视频文案或上传视频继续分析。",
            error_code="unknown_error",
        )

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
    except Exception as error:
        error_code = _classify_metadata_error(error)
        return _fallback(webpage_url=url, error_code=error_code)

    if not isinstance(info, dict):
        return _fallback(webpage_url=url, error_code="metadata_blocked")

    formats = info.get("formats") or []
    downloadable = bool(info.get("url") or formats)
    if not downloadable:
        return _fallback(webpage_url=info.get("webpage_url") or url, error_code="not_downloadable")

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
        return _fallback(platform="unknown", reason="未识别到有效链接，请粘贴抖音分享链接或视频原文案。", error_code="non_douyin_url")

    try:
        expanded_url = await expand_short_url(extracted_url)
    except httpx.TimeoutException:
        return _fallback(webpage_url=extracted_url, error_code="redirect_timeout")
    except httpx.HTTPError:
        return _fallback(webpage_url=extracted_url, error_code="redirect_failed")
    except Exception:
        return _fallback(webpage_url=extracted_url, error_code="redirect_failed")

    if not is_douyin_url(expanded_url):
        return _fallback(platform="unknown", webpage_url=expanded_url, reason=ERROR_MESSAGES["non_douyin_url"], error_code="non_douyin_url")

    return await asyncio.to_thread(_metadata_with_ytdlp, expanded_url)


async def check_video_link(source_url: str) -> dict[str, Any]:
    extracted_url = extract_first_url(source_url)
    if not extracted_url:
        payload = _fallback(platform="unknown", reason="未识别到有效链接，请粘贴抖音分享链接或视频原文案。", error_code="non_douyin_url")
        return {**payload, "redirect_ok": False, "supported_platform": False, "next_step": payload["message"]}

    redirect_ok = True
    try:
        expanded_url = await expand_short_url(extracted_url)
    except httpx.TimeoutException:
        payload = _fallback(webpage_url=extracted_url, error_code="redirect_timeout")
        return {**payload, "redirect_ok": False, "supported_platform": False, "next_step": payload["message"]}
    except httpx.HTTPError:
        payload = _fallback(webpage_url=extracted_url, error_code="redirect_failed")
        return {**payload, "redirect_ok": False, "supported_platform": False, "next_step": payload["message"]}
    except Exception:
        payload = _fallback(webpage_url=extracted_url, error_code="redirect_failed")
        return {**payload, "redirect_ok": False, "supported_platform": False, "next_step": payload["message"]}

    if not is_douyin_url(expanded_url):
        payload = _fallback(platform="unknown", webpage_url=expanded_url, reason=ERROR_MESSAGES["non_douyin_url"], error_code="non_douyin_url")
        return {**payload, "redirect_ok": redirect_ok, "supported_platform": False, "next_step": payload["message"]}

    payload = await asyncio.to_thread(_metadata_with_ytdlp, expanded_url)
    if payload.get("ok"):
        return {
            **payload,
            "redirect_ok": redirect_ok,
            "supported_platform": True,
            "next_step": "链接可自动读取，可以开始分析。",
        }
    return {
        **payload,
        "redirect_ok": redirect_ok,
        "supported_platform": True,
        "next_step": payload.get("message") or DOUYIN_FALLBACK,
    }
