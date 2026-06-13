from __future__ import annotations

from fastapi import HTTPException

from app.core.config import settings
from app.services.avatar_motion.base import AvatarMotionProvider
from app.services.avatar_motion.liveportrait_provider import LivePortraitProvider
from app.services.avatar_motion.replicate_liveportrait_provider import ReplicateLivePortraitProvider


def get_avatar_motion_provider() -> AvatarMotionProvider | None:
    provider = (settings.avatar_motion_provider or "static").strip().lower()
    if provider in {"", "static"}:
        return None
    if provider == "liveportrait":
        return LivePortraitProvider()
    if provider == "replicate":
        return ReplicateLivePortraitProvider()
    raise HTTPException(status_code=400, detail=f"Unsupported AVATAR_MOTION_PROVIDER: {settings.avatar_motion_provider}")


def liveportrait_configured() -> bool:
    return all(
        [
            settings.liveportrait_api_base_url.strip(),
            settings.liveportrait_api_key.strip(),
        ]
    )


def replicate_configured() -> bool:
    return all(
        [
            settings.replicate_api_token.strip(),
            settings.replicate_liveportrait_model.strip(),
        ]
    )
