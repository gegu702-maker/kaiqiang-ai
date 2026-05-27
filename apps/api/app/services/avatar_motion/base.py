from __future__ import annotations

from typing import Optional, Protocol


class AvatarMotionProvider(Protocol):
    async def generate_avatar_motion(
        self,
        *,
        source_image_url: str,
        audio_url: str,
        driving_video_url: Optional[str],
        task_id: str,
    ) -> str:
        """Return a generated dynamic avatar video URL."""
