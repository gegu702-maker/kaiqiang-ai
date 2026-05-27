from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.services.avatar_motion.base import AvatarMotionProvider


class LivePortraitProvider(AvatarMotionProvider):
    async def generate_avatar_motion(
        self,
        *,
        source_image_url: str,
        audio_url: str,
        driving_video_url: Optional[str],
        task_id: str,
    ) -> str:
        self._validate()
        selected_driving_video_url = driving_video_url or settings.liveportrait_default_driving_video_url.strip()
        payload = {
            "source_image_url": source_image_url,
            "audio_url": audio_url,
            "driving_video_url": selected_driving_video_url,
            "task_id": task_id,
        }
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{settings.liveportrait_api_base_url.rstrip('/')}/generate",
                headers={
                    "Authorization": f"Bearer {settings.liveportrait_api_key.strip()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        data = self._parse_json(response)
        if not response.is_success:
            raise HTTPException(status_code=502, detail=self._error_detail(data, response.text))
        if data.get("success") and data.get("video_url"):
            return str(data["video_url"])
        job_id = data.get("job_id")
        polling_url = data.get("polling_url")
        if job_id and polling_url:
            return await self._poll_job(str(polling_url), str(job_id))
        raise HTTPException(
            status_code=502,
            detail={
                "message": "LivePortrait API did not return video_url",
                "job_id": job_id,
                "polling_url": polling_url,
                "status": data.get("status"),
                "error": data.get("error"),
            },
        )

    async def _poll_job(self, polling_url: str, job_id: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            for _ in range(30):
                response = await client.get(
                    polling_url,
                    headers={"Authorization": f"Bearer {settings.liveportrait_api_key.strip()}"},
                )
                data = self._parse_json(response)
                if not response.is_success:
                    raise HTTPException(status_code=502, detail=self._error_detail(data, response.text))
                if data.get("success") and data.get("video_url"):
                    return str(data["video_url"])
                status = str(data.get("status") or "").lower()
                if status in {"failed", "error", "canceled", "cancelled"}:
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "message": "LivePortrait job failed",
                            "job_id": job_id,
                            "polling_url": polling_url,
                            "status": data.get("status"),
                            "error": data.get("error"),
                        },
                    )
                await asyncio.sleep(5)
        raise HTTPException(
            status_code=504,
            detail={
                "message": "LivePortrait job polling timed out",
                "job_id": job_id,
                "polling_url": polling_url,
                "status": "timeout",
            },
        )

    def _validate(self) -> None:
        if not settings.liveportrait_api_base_url.strip():
            raise HTTPException(status_code=400, detail="LIVEPORTRAIT_API_BASE_URL missing")
        if not settings.liveportrait_api_key.strip():
            raise HTTPException(status_code=400, detail="LIVEPORTRAIT_API_KEY missing")
        if not settings.liveportrait_default_driving_video_url.strip():
            raise HTTPException(status_code=400, detail="LIVEPORTRAIT_DEFAULT_DRIVING_VIDEO_URL missing")

    def _parse_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else {"data": payload}
        except ValueError:
            return {}

    def _error_detail(self, data: dict[str, Any], raw: str) -> dict[str, Any] | str:
        if data:
            return {
                "message": data.get("message") or data.get("detail") or "LivePortrait API error",
                "job_id": data.get("job_id"),
                "polling_url": data.get("polling_url"),
                "status": data.get("status"),
                "error": data.get("error"),
            }
        return raw[:800] or "LivePortrait API error"
