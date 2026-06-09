from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

DOUYIN_FALLBACK = "当前抖音链接暂时无法自动解析，请粘贴视频文案或上传视频继续分析。"
URL_RE = re.compile(
    r"(?:(?:https?://)?(?:v\.)?douyin\.com|(?:https?://)?(?:www\.)?iesdouyin\.com|https?://[^\s\"'<>，。；、]+)"
    r"[^\s\"'<>，。；、]*",
    re.IGNORECASE,
)
TRAILING_URL_PUNCTUATION = ")]}>,.，。；;、！!？?"
DOUYIN_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://www.douyin.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
FALLBACK_ACTIONS = ["upload_video", "paste_script", "check_link"]

ERROR_MESSAGES = {
    "no_url": "未识别到有效链接，请粘贴抖音分享链接，或上传视频/粘贴文案继续。",
    "non_douyin_url": "当前阶段优先支持抖音链接，请粘贴抖音链接，或上传视频/粘贴文案继续。",
    "redirect_failed": "抖音短链展开失败，请检查链接是否完整，或上传视频/粘贴文案继续。",
    "redirect_timeout": "抖音短链展开超时，请稍后重试，或上传视频/粘贴文案继续。",
    "metadata_blocked": "抖音暂时限制了自动读取，请上传视频或粘贴原文案继续分析。",
    "not_downloadable": "已识别抖音链接，但暂时拿不到可下载视频，请上传视频或粘贴文案继续。",
    "resolver_timeout": "链接解析超时，请稍后重试，或上传视频/粘贴文案继续。",
    "unknown_error": DOUYIN_FALLBACK,
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
    input_url: str = ""
    fallback_actions: list[str] | None = None

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
            "error_code": self.error_code,
            "errorCode": self.error_code,
            "input_url": self.input_url,
            "inputUrl": self.input_url,
            "fallback_actions": self.fallback_actions or [],
            "fallbackActions": self.fallback_actions or [],
        }


class ResolverError(Exception):
    def __init__(self, error_code: str, message: str | None = None):
        self.error_code = error_code
        super().__init__(message or ERROR_MESSAGES.get(error_code, DOUYIN_FALLBACK))


def _normalize_url(value: str) -> str:
    cleaned = (value or "").strip().rstrip(TRAILING_URL_PUNCTUATION)
    if cleaned and not urlparse(cleaned).scheme:
        cleaned = f"https://{cleaned}"
    return cleaned


def extract_urls(value: str) -> list[str]:
    matches = [_normalize_url(match.group(0)) for match in URL_RE.finditer(value or "")]
    deduped: list[str] = []
    for url in matches:
        if url and url not in deduped:
            deduped.append(url)
    return deduped


def extract_best_url(value: str) -> str:
    urls = extract_urls(value)
    douyin_urls = [url for url in urls if is_douyin_url(url)]
    if douyin_urls:
        return douyin_urls[0]
    return urls[0] if urls else ""


def is_douyin_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host == "douyin.com" or host.endswith(".douyin.com") or host.endswith(".iesdouyin.com")


def is_douyin_short_url(url: str) -> bool:
    return urlparse(url).netloc.lower() == "v.douyin.com"


async def expand_short_url(url: str) -> str:
    if not is_douyin_short_url(url):
        return url
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15, headers=DOUYIN_REQUEST_HEADERS) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.TimeoutException as error:
        raise ResolverError("redirect_timeout") from error
    except httpx.HTTPError as error:
        raise ResolverError("redirect_failed") from error
    return str(response.url)


def _fallback(
    *,
    platform: str = "douyin",
    webpage_url: str = "",
    reason: str | None = None,
    error_code: str = "unknown_error",
    input_url: str = "",
) -> dict[str, Any]:
    return ResolvedVideoLink(
        ok=False,
        platform=platform,
        webpage_url=webpage_url,
        downloadable=False,
        fallback_reason=reason or ERROR_MESSAGES.get(error_code, DOUYIN_FALLBACK),
        error_code=error_code,
        input_url=input_url,
        fallback_actions=FALLBACK_ACTIONS,
    ).to_dict()


def _metadata_with_ytdlp(url: str) -> dict[str, Any]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return _fallback(
            webpage_url=url,
            reason="服务端未安装 yt-dlp，暂时无法自动解析抖音链接，请粘贴视频文案或上传视频继续分析。",
            error_code="unknown_error",
            input_url=url,
        )

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
        "http_headers": DOUYIN_REQUEST_HEADERS,
        "retries": 3,
        "extractor_retries": 3,
        "socket_timeout": 20,
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as error:
        message = str(error).lower()
        if "timed out" in message or "timeout" in message:
            return _fallback(webpage_url=url, error_code="resolver_timeout", input_url=url)
        if any(token in message for token in ["403", "forbidden", "blocked", "captcha", "cookies", "login", "sign in"]):
            return _fallback(webpage_url=url, error_code="metadata_blocked", input_url=url)
        if "unsupported url" in message or "no video formats" in message:
            return _fallback(webpage_url=url, error_code="not_downloadable", input_url=url)
        return _fallback(webpage_url=url, error_code="unknown_error", input_url=url)

    if not isinstance(info, dict):
        return _fallback(webpage_url=url, error_code="unknown_error", input_url=url)

    formats = info.get("formats") or []
    downloadable = bool(info.get("url") or formats)
    if not downloadable:
        return _fallback(webpage_url=info.get("webpage_url") or url, error_code="not_downloadable", input_url=url)

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
        error_code="",
        input_url=url,
        fallback_actions=[],
    ).to_dict()


async def resolve_video_link(source_url: str) -> dict[str, Any]:
    extracted_url = extract_best_url(source_url)
    if not extracted_url:
        return _fallback(platform="unknown", error_code="no_url", input_url=source_url)

    try:
        expanded_url = await expand_short_url(extracted_url)
    except ResolverError as error:
        return _fallback(webpage_url=extracted_url, error_code=error.error_code, input_url=source_url)

    if not is_douyin_url(expanded_url):
        return _fallback(platform="unknown", webpage_url=expanded_url, error_code="non_douyin_url", input_url=source_url)

    return await asyncio.to_thread(_metadata_with_ytdlp, expanded_url)
