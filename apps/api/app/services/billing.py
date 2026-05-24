from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from supabase import Client

PLAN_QUOTAS: dict[str, int | None] = {
    "free": 3,
    "pro": 100,
    "business": None,
}


def current_period_start() -> str:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def ensure_profile(supabase: Client, *, user_id: str, email: str) -> dict[str, Any]:
    result = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    if result.data:
        return result.data[0]

    payload = {
        "id": user_id,
        "email": email,
        "plan": "free",
        "monthly_quota": PLAN_QUOTAS["free"],
    }
    created = supabase.table("profiles").insert(payload).execute()
    return created.data[0]


def get_usage_summary(supabase: Client, *, user_id: str, email: str) -> dict[str, Any]:
    profile = ensure_profile(supabase, user_id=user_id, email=email)
    plan = profile.get("plan") or "free"
    quota = profile.get("custom_quota")
    if quota is None:
        quota = profile.get("monthly_quota")
    if quota is None and plan in PLAN_QUOTAS:
        quota = PLAN_QUOTAS[plan]

    period = current_period_start()
    logs = (
        supabase.table("usage_logs")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("action", "generate_video")
        .gte("created_at", period)
        .execute()
    )
    used = logs.count or 0
    remaining = None if quota is None else max(int(quota) - used, 0)

    return {
        "plan": plan,
        "monthly_quota": quota,
        "used": used,
        "remaining": remaining,
        "period_start": period,
    }


def assert_generation_quota(supabase: Client, *, user_id: str, email: str) -> dict[str, Any]:
    usage = get_usage_summary(supabase, user_id=user_id, email=email)
    if usage["remaining"] is not None and usage["remaining"] <= 0:
        raise HTTPException(status_code=402, detail="本月生成额度已用完，请升级套餐。")
    return usage


def log_generation_usage(supabase: Client, *, user_id: str, task_id: str) -> None:
    supabase.table("usage_logs").insert(
        {
            "user_id": user_id,
            "task_id": task_id,
            "action": "generate_video",
            "quantity": 1,
            "period_start": current_period_start(),
        }
    ).execute()
