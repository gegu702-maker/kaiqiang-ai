from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from supabase import Client

from app.core.config import settings
from app.core.supabase import get_supabase
from app.models.video_task import TaskStatus, VideoTask
from app.services.billing import list_admin_orders, list_admin_users, mark_order_paid_and_upgrade, update_profile_admin
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


@router.get("/users", dependencies=[Depends(verify_admin)])
def get_admin_users(supabase: Client = Depends(get_supabase)) -> list[dict]:
    return list_admin_users(supabase)


@router.get("/orders", dependencies=[Depends(verify_admin)])
def get_orders(supabase: Client = Depends(get_supabase)) -> list[dict]:
    return list_admin_orders(supabase)


@router.patch("/users/{user_id}", dependencies=[Depends(verify_admin)])
def patch_user_profile(
    user_id: str,
    plan: str | None = Form(default=None),
    monthly_quota: int | None = Form(default=None),
    custom_quota: int | None = Form(default=None),
    voice_clone_enabled: bool | None = Form(default=None),
    status: str | None = Form(default=None),
    supabase: Client = Depends(get_supabase),
) -> dict:
    if plan and plan not in {"free", "plus", "pro", "business"}:
        raise HTTPException(status_code=400, detail="Invalid plan")
    if status and status not in {"active", "banned"}:
        raise HTTPException(status_code=400, detail="Invalid user status")
    return update_profile_admin(
        supabase,
        user_id=user_id,
        plan=plan,
        monthly_quota=monthly_quota,
        custom_quota=custom_quota,
        voice_clone_enabled=voice_clone_enabled,
        status=status,
    )


@router.post("/orders/{order_id}/mark-paid", dependencies=[Depends(verify_admin)])
def mark_order_paid(
    order_id: str,
    provider_payment_id: str = Form(default="manual-admin"),
    supabase: Client = Depends(get_supabase),
) -> dict:
    order = mark_order_paid_and_upgrade(supabase, order_id=order_id, provider_payment_id=provider_payment_id)
    return {"ok": True, "order": order}


@router.get("/tasks/{task_id}/logs", dependencies=[Depends(verify_admin)])
def get_task_logs(task_id: str, supabase: Client = Depends(get_supabase)) -> list[dict]:
    result = (
        supabase.table("task_logs")
        .select("*")
        .eq("task_id", task_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return result.data


@router.post("/tasks/{task_id}/retry", response_model=VideoTask, dependencies=[Depends(verify_admin)])
def retry_admin_task(task_id: str, supabase: Client = Depends(get_supabase)) -> VideoTask:
    task = get_task(supabase, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    supabase.table("video_tasks").update({"status": "waiting", "generation_error": ""}).eq("id", task_id).execute()
    existing = supabase.table("task_queue").select("id").eq("task_id", task_id).limit(1).execute()
    if existing.data:
        supabase.table("task_queue").update({"status": "waiting", "attempts": 0, "error_message": ""}).eq("task_id", task_id).execute()
    else:
        supabase.table("task_queue").insert({"task_id": task_id, "user_id": task.get("user_id"), "status": "waiting"}).execute()
    updated = get_task(supabase, task_id)
    return VideoTask(**updated)
