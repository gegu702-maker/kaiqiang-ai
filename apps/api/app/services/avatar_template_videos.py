from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException

from app.core.config import settings

MISSING_TEMPLATE_VIDEO_MESSAGE = "当前数字人模板暂未配置动态视频素材，请选择其他模板。"


def get_dynamic_template_video_url(avatar_template_id: str | None) -> str:
    selected = (avatar_template_id or "").strip()
    template_urls = _parse_template_video_urls()
    if selected:
        video_url = template_urls.get(selected, "").strip()
        if video_url:
            return video_url
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_template_video",
                "message": MISSING_TEMPLATE_VIDEO_MESSAGE,
                "avatar_template_id": selected,
                "missing_template_video": True,
            },
        )

    default_video_url = settings.musetalk_default_template_video_url.strip()
    if default_video_url:
        return default_video_url
    raise HTTPException(
        status_code=400,
        detail={
            "error": "missing_template_video",
            "message": MISSING_TEMPLATE_VIDEO_MESSAGE,
            "avatar_template_id": "",
            "missing_template_video": True,
        },
    )


def _parse_template_video_urls() -> dict[str, str]:
    raw = settings.musetalk_template_video_urls.strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "invalid_template_video_urls",
                "message": "MUSE_TALK_TEMPLATE_VIDEO_URLS must be valid JSON.",
            },
        ) from error
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "invalid_template_video_urls",
                "message": "MUSE_TALK_TEMPLATE_VIDEO_URLS must be a JSON object.",
            },
        )
    return {str(key): str(value) for key, value in payload.items() if isinstance(value, str) and value.strip()}
