from __future__ import annotations

import json
from fastapi import HTTPException

from app.core.config import settings

MISSING_TEMPLATE_VIDEO_MESSAGE = "当前数字人模板暂未配置动态视频素材，请选择其他模板。"
DEFAULT_TEMPLATE_VIDEO_URLS = {
    "business_female_01": "https://povfvhdnrpytxbbyndit.supabase.co/storage/v1/object/public/videos/avatars/business_female_01_v2.mp4?",
    "business_male_01": "https://povfvhdnrpytxbbyndit.supabase.co/storage/v1/object/public/videos/avatars/business_male_01_v3.mp4?",
}


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
                "success": False,
                "code": "missing_template_video",
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
            "success": False,
            "code": "missing_template_video",
            "error": "missing_template_video",
            "message": MISSING_TEMPLATE_VIDEO_MESSAGE,
            "avatar_template_id": "",
            "missing_template_video": True,
        },
    )


def _parse_template_video_urls() -> dict[str, str]:
    template_urls = dict(DEFAULT_TEMPLATE_VIDEO_URLS)
    raw = settings.musetalk_template_video_urls.strip()
    if not raw:
        return template_urls
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
    template_urls.update({str(key): str(value) for key, value in payload.items() if isinstance(value, str) and value.strip()})
    return template_urls
