from __future__ import annotations

import asyncio

import httpx
from fastapi import HTTPException
from supabase import Client

from app.core.config import settings


def _format_heygen_error(status_code: int, body: str) -> str:
    if status_code in {401, 403}:
        return (
            "HeyGen API 权限不足或 API Key 无效。请检查 HEYGEN_API_KEY 是否可用于 API 调用，"
            "当前套餐是否支持 custom avatar / avatar video generation。"
            f" HeyGen 返回：{body[:500]}"
        )
    if status_code in {402, 429}:
        return (
            "HeyGen 额度不足、试用版限制或请求频率受限。请检查账号余额、API credits、视频生成额度和套餐权限。"
            f" HeyGen 返回：{body[:500]}"
        )
    return f"HeyGen video generation failed ({status_code}): {body[:800]}"


async def generate_avatar_video(
    supabase: Client,
    *,
    audio_url: str,
    avatar_id: str,
    scene_prompt: str,
) -> dict:
    del supabase
    if not settings.heygen_api_key:
        return {
            "talking_video_url": None,
            "provider": "none",
            "status": "skipped",
            "message": "HEYGEN_API_KEY 未配置，本次使用 FFmpeg 商品图视频合成。",
        }

    heygen_avatar_id = avatar_id if avatar_id and avatar_id != "heygen_custom" else settings.heygen_avatar_id
    if not heygen_avatar_id:
        return {
            "talking_video_url": None,
            "provider": "heygen",
            "status": "skipped",
            "message": "HEYGEN_AVATAR_ID 未配置。",
        }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.heygen.com/v2/video/generate",
            headers={"X-Api-Key": settings.heygen_api_key},
            json={
                "video_inputs": [
                    {
                        "character": {
                            "type": "avatar",
                            "avatar_id": heygen_avatar_id,
                            "avatar_style": "normal",
                        },
                        "voice": {
                            "type": "audio",
                            "audio_url": audio_url,
                        },
                        "background": {
                            "type": "color",
                            "value": "#0b111c",
                        },
                    }
                ],
                "dimension": {"width": 720, "height": 1280},
                "caption": True,
                "title": scene_prompt[:80],
            },
        )
    if response.status_code >= 400:
        message = _format_heygen_error(response.status_code, response.text)
        if response.status_code in {401, 402, 403, 429}:
            raise HTTPException(status_code=502, detail=message)
        return {
            "talking_video_url": None,
            "provider": "heygen",
            "status": "failed",
            "message": message,
        }

    video_id = (response.json().get("data") or {}).get("video_id")
    if not video_id:
        return {"talking_video_url": None, "provider": "heygen", "status": "failed", "message": "HeyGen missing video_id"}

    video_url = await _poll_heygen_video(video_id)
    return {
        "talking_video_url": video_url,
        "provider": "heygen",
        "status": "success" if video_url else "rendering",
        "video_id": video_id,
    }


async def _poll_heygen_video(video_id: str) -> str | None:
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(40):
            await asyncio.sleep(8)
            response = await client.get(
                "https://api.heygen.com/v1/video_status.get",
                headers={"X-Api-Key": settings.heygen_api_key},
                params={"video_id": video_id},
            )
            if response.status_code >= 400:
                if response.status_code in {401, 402, 403, 429}:
                    raise HTTPException(status_code=502, detail=_format_heygen_error(response.status_code, response.text))
                continue
            data = response.json().get("data") or {}
            if data.get("status") == "completed":
                return data.get("video_url")
            if data.get("status") == "failed":
                return None
    return None
