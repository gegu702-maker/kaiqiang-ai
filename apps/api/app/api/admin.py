import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from postgrest.exceptions import APIError
from supabase import Client

from app.core.config import settings
from app.core.supabase import get_supabase
from app.models.video_task import TaskStatus, VideoTask
from app.services.billing import (
    list_admin_orders,
    list_admin_payments,
    list_admin_plans,
    list_admin_quotas,
    list_admin_subscriptions,
    list_admin_users,
    mark_order_paid_and_upgrade,
    update_plan_admin,
    update_profile_admin,
    update_quota_admin,
)
from app.services.storage import upload_public_bytes, upload_public_file
from app.services.subtitles import build_script_webvtt
from app.services.tasks import get_task, list_all_tasks, update_task

router = APIRouter(tags=["admin"])
VIDEO_EXTENSIONS = {".mp4"}
VIDEO_TYPES = {"video/mp4", "application/mp4"}
MB = 1024 * 1024


def verify_admin(x_admin_key: str = Header(...)) -> None:
    candidate = x_admin_key.replace("ADMIN_API_KEY=", "", 1).strip()
    expected = settings.admin_api_key.strip()
    if not expected:
        raise HTTPException(status_code=500, detail="ADMIN_API_KEY is not configured on API service")
    if not secrets.compare_digest(candidate, expected):
        raise HTTPException(status_code=401, detail="Invalid admin key")


def _missing_generation_error_column(error: APIError) -> bool:
    message = str(error)
    return "generation_error" in message and ("PGRST204" in message or "schema cache" in message)


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


@router.get("/subscriptions", dependencies=[Depends(verify_admin)])
def get_subscriptions(supabase: Client = Depends(get_supabase)) -> list[dict]:
    return list_admin_subscriptions(supabase)


@router.get("/payments", dependencies=[Depends(verify_admin)])
def get_payments(supabase: Client = Depends(get_supabase)) -> list[dict]:
    return list_admin_payments(supabase)


@router.get("/plans", dependencies=[Depends(verify_admin)])
def get_plans(supabase: Client = Depends(get_supabase)) -> list[dict]:
    return list_admin_plans(supabase)


@router.patch("/plans/{code}", dependencies=[Depends(verify_admin)])
def patch_plan(
    code: str,
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    monthly_quota: int | None = Form(default=None),
    monthly_quota_unlimited: bool = Form(default=False),
    monthly_price_cny: int | None = Form(default=None),
    yearly_price_cny: int | None = Form(default=None),
    voice_clone_enabled: bool | None = Form(default=None),
    is_active: bool | None = Form(default=None),
    sort_order: int | None = Form(default=None),
    supabase: Client = Depends(get_supabase),
) -> dict:
    return update_plan_admin(
        supabase,
        code=code,
        name=name,
        description=description,
        monthly_quota=monthly_quota,
        monthly_quota_unlimited=monthly_quota_unlimited,
        monthly_price_cny=monthly_price_cny,
        yearly_price_cny=yearly_price_cny,
        voice_clone_enabled=voice_clone_enabled,
        is_active=is_active,
        sort_order=sort_order,
    )


@router.get("/quotas", dependencies=[Depends(verify_admin)])
def get_quotas(supabase: Client = Depends(get_supabase)) -> list[dict]:
    return list_admin_quotas(supabase)


@router.patch("/quotas/{quota_id}", dependencies=[Depends(verify_admin)])
def patch_quota(
    quota_id: str,
    monthly_limit: int | None = Form(default=None),
    used_count: int | None = Form(default=None),
    remaining_count: int | None = Form(default=None),
    supabase: Client = Depends(get_supabase),
) -> dict:
    return update_quota_admin(
        supabase,
        quota_id=quota_id,
        monthly_limit=monthly_limit,
        used_count=used_count,
        remaining_count=remaining_count,
    )


def _count_table(supabase: Client, table: str, *, created_since: str | None = None) -> int:
    query = supabase.table(table).select("id", count="exact").limit(1)
    if created_since:
        query = query.gte("created_at", created_since)
    result = query.execute()
    return result.count or 0


@router.get("/stats", dependencies=[Depends(verify_admin)])
def get_admin_stats(supabase: Client = Depends(get_supabase)) -> dict:
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    users = list_admin_users(supabase)
    return {
        "totalUsers": len(users),
        "freeUsers": sum(1 for user in users if user.get("plan") == "free"),
        "businessUsers": sum(1 for user in users if user.get("plan") == "business"),
        "waitlistCount": _count_table(supabase, "waitlist"),
        "avatarGenerations": _count_table(supabase, "avatar_tasks"),
        "todayGenerations": _count_table(supabase, "avatar_tasks", created_since=today_start),
        "todayRegistrations": sum(1 for user in users if str(user.get("created_at") or "") >= today_start),
        "supabaseServiceRoleKeyConfigured": bool(settings.supabase_service_role_key.strip()),
    }


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
    try:
        supabase.table("video_tasks").update({"status": "waiting", "generation_error": ""}).eq("id", task_id).execute()
    except APIError as error:
        if not _missing_generation_error_column(error):
            raise
        supabase.table("video_tasks").update({"status": "waiting"}).eq("id", task_id).execute()
    existing = supabase.table("task_queue").select("id").eq("task_id", task_id).limit(1).execute()
    if existing.data:
        supabase.table("task_queue").update({"status": "waiting", "attempts": 0, "error_message": ""}).eq("task_id", task_id).execute()
    else:
        supabase.table("task_queue").insert({"task_id": task_id, "user_id": task.get("user_id"), "status": "waiting"}).execute()
    updated = get_task(supabase, task_id)
    return VideoTask(**updated)
