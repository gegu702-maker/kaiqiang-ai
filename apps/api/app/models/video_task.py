from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, EmailStr


class TaskStatus(str, Enum):
    pending = "pending"
    scripting = "scripting"
    producing = "producing"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class SubtitleStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class CosyVoiceStatus(str, Enum):
    pending = "pending"
    generating = "generating"
    completed = "completed"
    failed = "failed"


class VideoTask(BaseModel):
    id: str
    user_email: EmailStr
    product_name: str
    script: str
    language: str
    image_url: str
    personal_image_url: Optional[str] = None
    product_highlights: str = ""
    target_audience: str = ""
    video_style: str = ""
    use_digital_human: bool = True
    production_mode: str = "semi_auto"
    avatar_id: str
    voice_url: str
    tts_language: str
    tts_voice_name: str
    admin_notes: str = ""
    status: TaskStatus
    result_video_url: Optional[str] = None
    subtitle_url: Optional[str] = None
    subtitle_status: SubtitleStatus = SubtitleStatus.pending
    cloned_voice_url: Optional[str] = None
    cosyvoice_status: CosyVoiceStatus = CosyVoiceStatus.pending
    heygen_avatar_id: str = ""
    heygen_voice_id: str = ""
    heygen_video_id: str = ""
    heygen_video_url: str = ""
    selling_points: list[dict[str, Any]] = []
    hook: str = ""
    shot_list: list[dict[str, Any]] = []
    title_options: list[str] = []
    caption: str = ""
    cover_text: str = ""
    cover_prompt: str = ""
    hashtags: list[str] = []
    comment_prompt: str = ""
    closing_cta: str = ""
    admin_workflow: list[dict[str, Any]] = []
    created_at: datetime


class TaskCreateResponse(BaseModel):
    task: VideoTask


class CosyVoiceCloneResponse(BaseModel):
    audio_url: str
    local_path: str
    cosyvoice_status: CosyVoiceStatus = CosyVoiceStatus.completed
    task: Optional[VideoTask] = None
