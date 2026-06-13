from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from app.core.supabase import get_supabase
from app.services.avatar_motion.base import AvatarMotionProvider
from app.services.musetalk_client import generate_avatar_video_with_musetalk


class MuseTalkProvider(AvatarMotionProvider):
    async def generate_avatar_motion(
        self,
        *,
        source_image_url: str,
        audio_url: str,
        driving_video_url: Optional[str],
        task_id: str,
    ) -> str:
        template_video_url = (driving_video_url or "").strip()
        if not template_video_url:
            raise HTTPException(status_code=400, detail="MUSE_TALK_TEMPLATE_VIDEO_URLS missing template video URL")

        return await generate_avatar_video_with_musetalk(
            get_supabase(),
            video_url=template_video_url,
            audio_url=audio_url,
            task_id=task_id,
        )
