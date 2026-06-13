import logging
import traceback

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import EmailStr
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.config import settings
from app.core.supabase import get_supabase
from app.core.tts import MINIMAX_TTS_VOICES, get_tts_voice
from app.models.video_task import TaskCreateResponse, VideoTask
from app.services.avatar_templates import get_avatar_template
from app.services.content_ai import generate_commerce_package
from app.services.billing import assert_generation_quota, log_generation_usage
from app.services.storage import upload_public_file
from app.services.tasks import create_task, delete_user_task, get_user_task, list_user_tasks, requeue_user_task
from app.services.voice_clone_provider import assert_clone_owner, assert_user_can_clone

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)

ALLOWED_AVATARS = {"emily", "david", "sophia", "alex", "heygen_custom", "business_female_01", "business_male_01", "ai_female_01"}
ALLOWED_LANGUAGES = set(MINIMAX_TTS_VOICES.keys())
ALLOWED_VIDEO_STYLES = {"hard_sell", "emotional_seed", "premium", "factory_boss", "tiktok", "review", "story"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
VOICE_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".mpeg"}
VOICE_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/x-mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/m4a",
    "audio/x-m4a",
    "audio/mp4",
    "audio/aac",
    "audio/x-aac",
    "audio/mp4a-latm",
    "video/mp4",
    "application/octet-stream",
}
MB = 1024 * 1024


@router.post("", response_model=TaskCreateResponse)
async def create_video_task(
    user_email: EmailStr = Form(...),
    product_name: str = Form(...),
    product_highlights: str = Form(...),
    target_audience: str = Form(...),
    video_style: str = Form(...),
    use_digital_human: bool = Form(default=True),
    language: str = Form(...),
    voice_type: str | None = Form(default=None),
    avatar_id: str = Form(...),
    avatar_template_id: str | None = Form(default=None),
    use_cloned_voice: bool = Form(default=False),
    voice_clone_id: str | None = Form(default=None),
    image: UploadFile = File(...),
    personal_image: UploadFile | None = File(default=None),
    voice: UploadFile | None = File(default=None),
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> TaskCreateResponse:
    try:
        user = get_authenticated_user(supabase, token)
        if str(user_email).lower() != str(user["email"]).lower():
            raise HTTPException(status_code=403, detail="只能为当前登录账户创建任务。")
        assert_generation_quota(supabase, user_id=user["id"], email=user["email"])

        template = get_avatar_template(avatar_template_id or avatar_id if avatar_id in {"business_female_01", "business_male_01", "ai_female_01"} else avatar_template_id)
        selected_avatar_id = template.id
        if selected_avatar_id not in ALLOWED_AVATARS:
            raise HTTPException(status_code=400, detail="Invalid avatar_id")

        if language not in ALLOWED_LANGUAGES:
            raise HTTPException(status_code=400, detail="Language must be one of zh, en, ja, ko, es, fr, ru")
        if video_style not in ALLOWED_VIDEO_STYLES:
            raise HTTPException(status_code=400, detail="Invalid video_style")

        tts_voice = get_tts_voice(language)
        selected_tts_voice_name = (voice_type or "").strip() or template.voice_type or tts_voice.voice_name
        ai_package = generate_commerce_package(
            product_name=product_name,
            product_highlights=product_highlights,
            target_audience=target_audience,
            video_style=video_style,
            use_digital_human=use_digital_human,
        )

        image_url = await upload_public_file(
            supabase,
            settings.supabase_image_bucket,
            image,
            "products",
            allowed_extensions=IMAGE_EXTENSIONS,
            allowed_content_types=IMAGE_TYPES,
            max_bytes=10 * MB,
            allowed_format_label="jpg, jpeg, png, webp",
        )
        if use_digital_human and not template and (not personal_image or not personal_image.filename):
            raise HTTPException(status_code=400, detail="personal_image is required when use_digital_human=true")

        personal_image_url = None
        if personal_image and personal_image.filename:
            personal_image_url = await upload_public_file(
                supabase,
                settings.supabase_image_bucket,
                personal_image,
                "personal",
                allowed_extensions=IMAGE_EXTENSIONS,
                allowed_content_types=IMAGE_TYPES,
                max_bytes=10 * MB,
                allowed_format_label="jpg, jpeg, png, webp",
            )
        voice_url = ""
        selected_clone = None
        if use_cloned_voice:
            assert_user_can_clone(supabase, user_id=user["id"], email=user["email"])
            if not voice_clone_id:
                raise HTTPException(status_code=400, detail="voice_clone_id is required when use_cloned_voice=true")
            selected_clone = assert_clone_owner(supabase, user_id=user["id"], voice_clone_id=voice_clone_id)
            voice_url = selected_clone.get("sample_audio_url") or ""
        elif voice and voice.filename:
            voice_url = await upload_public_file(
                supabase,
                settings.supabase_voice_bucket,
                voice,
                "voices",
                allowed_extensions=VOICE_EXTENSIONS,
                allowed_content_types=VOICE_TYPES,
                max_bytes=20 * MB,
                allowed_format_label="mp3, wav, m4a",
            )
        task = create_task(
            supabase,
            user_id=user["id"],
            user_email=str(user_email),
            product_name=product_name,
            script=ai_package["script"],
            product_highlights=product_highlights,
            target_audience=target_audience,
            video_style=video_style,
            use_digital_human=use_digital_human,
            ai_package=ai_package,
            language=language,
            image_url=image_url,
            personal_image_url=personal_image_url,
            avatar_id=selected_avatar_id,
            voice_url=voice_url,
            voice_clone_id=voice_clone_id if use_cloned_voice else None,
            use_cloned_voice=use_cloned_voice,
            tts_language=tts_voice.language,
            tts_voice_name=selected_tts_voice_name,
        )
        log_generation_usage(supabase, user_id=user["id"], task_id=task["id"])
        return TaskCreateResponse(task=VideoTask(**task))
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Failed to create video task")
        raise HTTPException(
            status_code=500,
            detail={
                "message": str(error),
                "type": error.__class__.__name__,
                "traceback": traceback.format_exc()[-6000:],
            },
        ) from error


@router.get("", response_model=list[VideoTask])
def get_tasks(
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> list[VideoTask]:
    user = get_authenticated_user(supabase, token)
    return [VideoTask(**task) for task in list_user_tasks(supabase, user["id"])]


@router.get("/{task_id}", response_model=VideoTask)
def get_task_detail(
    task_id: str,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> VideoTask:
    user = get_authenticated_user(supabase, token)
    task = get_user_task(supabase, task_id, user["id"])
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return VideoTask(**task)


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    delete_user_task(supabase, task_id, user["id"])
    return {"ok": True}


@router.post("/{task_id}/retry", response_model=VideoTask)
def retry_task(
    task_id: str,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> VideoTask:
    user = get_authenticated_user(supabase, token)
    try:
        task = requeue_user_task(supabase, task_id, user["id"])
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found") from None
    return VideoTask(**task)
