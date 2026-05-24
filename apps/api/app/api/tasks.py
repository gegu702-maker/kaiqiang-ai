from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import EmailStr
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.config import settings
from app.core.supabase import get_supabase
from app.core.tts import MINIMAX_TTS_VOICES, get_tts_voice
from app.models.video_task import TaskCreateResponse, VideoTask
from app.services.content_ai import generate_commerce_package
from app.services.billing import assert_generation_quota, log_generation_usage
from app.services.storage import upload_public_file
from app.services.tasks import create_task, get_user_task, list_user_tasks

router = APIRouter(prefix="/tasks", tags=["tasks"])

ALLOWED_AVATARS = {"emily", "david", "sophia", "alex", "heygen_custom"}
ALLOWED_LANGUAGES = set(MINIMAX_TTS_VOICES.keys())
ALLOWED_VIDEO_STYLES = {"hard_sell", "emotional_seed", "review", "story"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
VOICE_EXTENSIONS = {".mp3", ".wav", ".m4a"}
VOICE_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/m4a",
    "audio/x-m4a",
    "audio/mp4",
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
    avatar_id: str = Form(...),
    image: UploadFile = File(...),
    personal_image: UploadFile = File(...),
    voice: UploadFile = File(...),
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> TaskCreateResponse:
    user = get_authenticated_user(supabase, token)
    if str(user_email).lower() != str(user["email"]).lower():
        raise HTTPException(status_code=403, detail="只能为当前登录账户创建任务。")
    assert_generation_quota(supabase, user_id=user["id"], email=user["email"])

    if avatar_id not in ALLOWED_AVATARS:
        raise HTTPException(status_code=400, detail="Invalid avatar_id")

    if language not in ALLOWED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Language must be zh or en")
    if video_style not in ALLOWED_VIDEO_STYLES:
        raise HTTPException(status_code=400, detail="Invalid video_style")

    tts_voice = get_tts_voice(language)
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
    )
    personal_image_url = await upload_public_file(
        supabase,
        settings.supabase_image_bucket,
        personal_image,
        "personal",
        allowed_extensions=IMAGE_EXTENSIONS,
        allowed_content_types=IMAGE_TYPES,
        max_bytes=10 * MB,
    )
    voice_url = await upload_public_file(
        supabase,
        settings.supabase_voice_bucket,
        voice,
        "voices",
        allowed_extensions=VOICE_EXTENSIONS,
        allowed_content_types=VOICE_TYPES,
        max_bytes=20 * MB,
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
        avatar_id=avatar_id,
        voice_url=voice_url,
        tts_language=tts_voice.language,
        tts_voice_name=tts_voice.voice_name,
    )
    log_generation_usage(supabase, user_id=user["id"], task_id=task["id"])
    return TaskCreateResponse(task=VideoTask(**task))


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
