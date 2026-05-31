from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.avatar_motion.base import AvatarMotionProvider
from app.services.storage import upload_public_bytes


class ReplicateLivePortraitProvider(AvatarMotionProvider):
    async def generate_avatar_motion(
        self,
        *,
        source_image_url: str,
        audio_url: str,
        driving_video_url: Optional[str],
        task_id: str,
    ) -> str:
        self._validate(source_image_url)
        selected_driving_video_url = (driving_video_url or settings.liveportrait_default_driving_video_url).strip()
        if not selected_driving_video_url:
            raise HTTPException(status_code=400, detail="LIVEPORTRAIT_DEFAULT_DRIVING_VIDEO_URL missing")

        prediction = await self._create_prediction(
            source_image_url=source_image_url,
            driving_video_url=selected_driving_video_url,
        )
        completed = await self._poll_prediction(prediction)
        output_video_url = self._extract_output_video_url(completed)
        video_bytes = await self._download_video(output_video_url)
        try:
            return upload_public_bytes(
                get_supabase(),
                settings.supabase_video_bucket,
                video_bytes,
                f"replicate/liveportrait/{task_id}",
                ".mp4",
                "video/mp4",
            )
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Supabase upload failed: {error}") from error

    async def _create_prediction(self, *, source_image_url: str, driving_video_url: str) -> dict[str, Any]:
        model = settings.replicate_liveportrait_model.strip()
        url = f"https://api.replicate.com/v1/models/{model}/predictions"
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.replicate_api_token.strip()}",
                    "Content-Type": "application/json",
                    "Prefer": "wait=5",
                },
                json={
                    "input": {
                        "face_image": source_image_url,
                        "driving_video": driving_video_url,
                    }
                },
            )
        data = self._parse_json(response)
        if not response.is_success:
            raise HTTPException(status_code=502, detail=self._replicate_error(data, response.text))
        return data

    async def _poll_prediction(self, prediction: dict[str, Any]) -> dict[str, Any]:
        get_url = prediction.get("urls", {}).get("get")
        prediction_id = prediction.get("id")
        if not get_url:
            raise HTTPException(status_code=502, detail="Replicate prediction polling URL missing")

        async with httpx.AsyncClient(timeout=60) as client:
            for _ in range(72):
                response = await client.get(
                    str(get_url),
                    headers={"Authorization": f"Bearer {settings.replicate_api_token.strip()}"},
                )
                data = self._parse_json(response)
                if not response.is_success:
                    raise HTTPException(status_code=502, detail=self._replicate_error(data, response.text))

                status = str(data.get("status") or "").lower()
                if status == "succeeded":
                    return data
                if status in {"failed", "canceled", "cancelled"}:
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "message": "Replicate prediction failed",
                            "prediction_id": prediction_id,
                            "status": data.get("status"),
                            "error": data.get("error"),
                        },
                    )
                await asyncio.sleep(5)

        raise HTTPException(
            status_code=504,
            detail={
                "message": "Replicate prediction timeout",
                "prediction_id": prediction_id,
                "status": "timeout",
            },
        )

    async def _download_video(self, output_video_url: str) -> bytes:
        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
            response = await client.get(output_video_url)
        if not response.is_success:
            raise HTTPException(status_code=502, detail=f"Replicate output video download failed: {response.status_code}")
        return response.content

    def _extract_output_video_url(self, prediction: dict[str, Any]) -> str:
        output = prediction.get("output")
        if isinstance(output, str) and output:
            return output
        if isinstance(output, list):
            for item in output:
                if isinstance(item, str) and item:
                    return item
                if isinstance(item, dict):
                    candidate = item.get("url") or item.get("video_url")
                    if candidate:
                        return str(candidate)
        if isinstance(output, dict):
            candidate = output.get("video_url") or output.get("url") or output.get("output")
            if candidate:
                return str(candidate)
        raise HTTPException(status_code=502, detail="Replicate output video missing")

    def _validate(self, source_image_url: str) -> None:
        if not settings.replicate_api_token.strip():
            raise HTTPException(status_code=400, detail="REPLICATE_API_TOKEN missing")
        if not settings.replicate_liveportrait_model.strip():
            raise HTTPException(status_code=400, detail="REPLICATE_LIVEPORTRAIT_MODEL missing")
        if not source_image_url.strip():
            raise HTTPException(status_code=400, detail="source_image_url missing")

    def _parse_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else {"data": payload}
        except ValueError:
            return {}

    def _replicate_error(self, data: dict[str, Any], raw: str) -> dict[str, Any] | str:
        if data:
            return {
                "message": data.get("detail") or data.get("error") or "Replicate prediction failed",
                "status": data.get("status"),
                "error": data.get("error"),
            }
        return raw[:800] or "Replicate prediction failed"
