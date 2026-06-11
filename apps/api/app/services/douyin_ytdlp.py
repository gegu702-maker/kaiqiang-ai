from __future__ import annotations

import os
import re
from typing import Literal
from urllib.parse import urlparse

from app.core.config import settings

DOUYIN_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://www.douyin.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

IESDOUYIN_SHARE_VIDEO_RE = re.compile(r"^/share/video/(?P<video_id>\d+)/?$")


def normalize_douyin_web_url(url: str) -> str:
    parsed = urlparse(url or "")
    host = parsed.netloc.lower()
    if host not in {"iesdouyin.com", "www.iesdouyin.com"}:
        return url

    match = IESDOUYIN_SHARE_VIDEO_RE.match(parsed.path)
    if not match:
        return url

    return f"https://www.douyin.com/video/{match.group('video_id')}"


def _add_cookiefile_if_available(options: dict) -> dict:
    cookie_file = settings.douyin_cookie_file.strip()
    if cookie_file and os.path.exists(cookie_file):
        options["cookiefile"] = cookie_file
    return options


def build_douyin_ytdlp_options(mode: Literal["metadata", "download"]) -> dict:
    options = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "http_headers": DOUYIN_REQUEST_HEADERS,
    }

    if mode == "metadata":
        options.update(
            {
                "skip_download": True,
                "noplaylist": True,
                "extract_flat": False,
                "socket_timeout": 20,
                "retries": 3,
                "extractor_retries": 3,
            }
        )
        return _add_cookiefile_if_available(options)

    options.update(
        {
            "format": "best[ext=mp4]/best",
            "noplaylist": True,
            "socket_timeout": 30,
            "retries": 2,
            "fragment_retries": 2,
        }
    )
    return _add_cookiefile_if_available(options)
