from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from supabase import Client

from app.core.config import settings
from app.core.supabase import get_supabase
from app.models.video_task import TaskStatus, VideoTask
from app.services.storage import upload_public_bytes, upload_public_file
from app.services.subtitles import build_script_webvtt
from app.services.tasks import get_task, list_all_tasks, update_task

router = APIRouter(tags=["admin"])
VIDEO_EXTENSIONS = {".mp4"}
VIDEO_TYPES = {"video/mp4", "application/mp4"}
MB = 1024 * 1024


def verify_admin(x_admin_key: str = Header(...)) -> None:
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.get("/tasks", response_model=list[VideoTask], dependencies=[Depends(verify_admin)])
def get_admin_tasks(supabase: Client = Depends(get_supabase)) -> list[VideoTask]:
    return [VideoTask(**task) for task in list_all_tasks(supabase)]


@router.get("/tasks/{task_id}", response_model=VideoTask, dependencies=[Depends(verify_admin)])
def get_admin_task(
    task_id: str,
    supabase: Client = Depends(get_supabase),
) -> VideoTask:
    task = get_task(supabase, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return VideoTask(**task)


@router.patch("/tasks/{task_id}", response_model=VideoTask, dependencies=[Depends(verify_admin)])
async def patch_admin_task(
    task_id: str,
    status: TaskStatus | None = Form(default=None),
    admin_notes: str | None = Form(default=None),
    heygen_avatar_id: str | None = Form(default=None),
    heygen_voice_id: str | None = Form(default=None),
    heygen_video_id: str | None = Form(default=None),
    heygen_video_url: str | None = Form(default=None),
    result_video: UploadFile | None = File(default=None),
    supabase: Client = Depends(get_supabase),
) -> VideoTask:
    result_video_url = None
    subtitle_url = None
    subtitle_status = None
    final_status = status
    if result_video and result_video.filename:
        result_video_url = await upload_public_file(
            supabase,
            settings.supabase_video_bucket,
            result_video,
            "results",
            allowed_extensions=VIDEO_EXTENSIONS,
            allowed_content_types=VIDEO_TYPES,
            max_bytes=200 * MB,
        )
        final_status = TaskStatus.completed
        source_task = get_task(supabase, task_id)
        if not source_task:
            raise HTTPException(status_code=404, detail="Task not found")
        try:
            subtitle_url = upload_public_bytes(
                supabase,
                settings.supabase_subtitle_bucket,
                build_script_webvtt(source_task["script"]),
                "webvtt",
                ".vtt",
                "text/vtt; charset=utf-8",
            )
            subtitle_status = "completed"
        except Exception:
            subtitle_status = "failed"

    task = update_task(
        supabase,
        task_id,
        status=final_status,
        result_video_url=result_video_url,
        subtitle_url=subtitle_url,
        subtitle_status=subtitle_status,
        admin_notes=admin_notes,
        heygen_avatar_id=heygen_avatar_id,
        heygen_voice_id=heygen_voice_id,
        heygen_video_id=heygen_video_id,
        heygen_video_url=heygen_video_url,
    )
    return VideoTask(**task)
