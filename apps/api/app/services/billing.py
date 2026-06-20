from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
import httpx
from postgrest.exceptions import APIError
from supabase import Client

from app.core.config import settings

PLAN_QUOTAS: dict[str, int | None] = {
    "free": 3,
    "plus": 1000,
    "pro": 3000,
    "business": None,
}

PLAN_PRICES: dict[str, dict[str, dict[str, int]]] = {
    "plus": {
        "monthly": {"CNY": 19900, "USD": 2900},
        "yearly": {"CNY": 199000, "USD": 29000},
    },
    "pro": {
        "monthly": {"CNY": 79900, "USD": 10900},
        "yearly": {"CNY": 799000, "USD": 109000},
    },
    "business": {
        "monthly": {"CNY": 0, "USD": 0},
        "yearly": {"CNY": 0, "USD": 0},
    },
}

PLAN_MONTHLY_QUOTAS = {
    "free": 3,
    "plus": 1000,
    "pro": 3000,
    "business": None,
}

VOICE_CLONE_PLANS = {"pro", "business"}
FREE_PLAN = "free"
FREE_MONTHLY_QUOTA = 3
DEFAULT_PLAN_ROWS: list[dict[str, Any]] = [
    {
        "code": "free",
        "name": "Free",
        "description": "免费体验额度",
        "monthly_quota": 3,
        "monthly_price_cny": 0,
        "yearly_price_cny": 0,
        "voice_clone_enabled": False,
        "is_active": True,
        "sort_order": 10,
    },
    {
        "code": "plus",
        "name": "Plus",
        "description": "轻量创作者套餐",
        "monthly_quota": 1000,
        "monthly_price_cny": 19900,
        "yearly_price_cny": 199000,
        "voice_clone_enabled": False,
        "is_active": True,
        "sort_order": 20,
    },
    {
        "code": "pro",
        "name": "Pro",
        "description": "专业创作者套餐",
        "monthly_quota": 3000,
        "monthly_price_cny": 79900,
        "yearly_price_cny": 799000,
        "voice_clone_enabled": True,
        "is_active": True,
        "sort_order": 30,
    },
    {
        "code": "business",
        "name": "Business",
        "description": "企业定制套餐",
        "monthly_quota": None,
        "monthly_price_cny": 0,
        "yearly_price_cny": 0,
        "voice_clone_enabled": True,
        "is_active": True,
        "sort_order": 40,
    },
]


def current_period_start() -> str:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def current_reset_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def _is_schema_or_table_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "schema cache",
            "pgrst",
            "does not exist",
            "could not find",
            "column",
            "relation",
        )
    )


def _free_profile(user_id: str, email: str) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": email,
        "plan": FREE_PLAN,
        "monthly_quota": FREE_MONTHLY_QUOTA,
        "custom_quota": None,
        "voice_clone_enabled": False,
        "default_voice_id": None,
        "status": "active",
    }


def ensure_profile(supabase: Client, *, user_id: str, email: str) -> dict[str, Any]:
    fallback = _free_profile(user_id, email)
    try:
        result = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if result.data:
            profile = {**fallback, **result.data[0]}
            if profile.get("status") == "banned":
                raise HTTPException(status_code=403, detail="账户已被禁用，请联系管理员。")
            _normalize_free_profile(supabase, profile)
            return profile
    except HTTPException:
        raise
    except APIError as error:
        if not _is_schema_or_table_error(error):
            raise
        return fallback

    payload = {
        "id": user_id,
        "email": email,
        "plan": FREE_PLAN,
        "monthly_quota": FREE_MONTHLY_QUOTA,
        "voice_clone_enabled": False,
        "status": "active",
    }
    for candidate in (
        payload,
        {"id": user_id, "email": email, "plan": FREE_PLAN, "monthly_quota": FREE_MONTHLY_QUOTA},
        {"id": user_id, "email": email},
    ):
        try:
            created = supabase.table("profiles").insert(candidate).execute()
            profile = {**fallback, **(created.data[0] if created.data else candidate)}
            _ensure_free_subscription(supabase, user_id=user_id)
            return profile
        except APIError as error:
            if "duplicate" in str(error).lower():
                return ensure_profile(supabase, user_id=user_id, email=email)
            if not _is_schema_or_table_error(error):
                raise
    return fallback


def _normalize_free_profile(supabase: Client, profile: dict[str, Any]) -> None:
    updates: dict[str, Any] = {}
    if not profile.get("plan"):
        updates["plan"] = FREE_PLAN
    if profile.get("monthly_quota") is None and profile.get("plan", FREE_PLAN) == FREE_PLAN:
        updates["monthly_quota"] = FREE_MONTHLY_QUOTA
    if not profile.get("status"):
        updates["status"] = "active"
    if not updates:
        _ensure_free_subscription(supabase, user_id=profile["id"])
        return
    updates["updated_at"] = datetime.now(UTC).isoformat()
    try:
        supabase.table("profiles").update(updates).eq("id", profile["id"]).execute()
    except APIError:
        pass
    _ensure_free_subscription(supabase, user_id=profile["id"])


def _ensure_free_subscription(supabase: Client, *, user_id: str) -> None:
    now = datetime.now(UTC)
    try:
        existing = (
            supabase.table("subscriptions")
            .select("id")
            .eq("user_id", user_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if existing.data:
            return
        supabase.table("subscriptions").insert(
            {
                "user_id": user_id,
                "plan": FREE_PLAN,
                "status": "active",
                "provider": "manual",
                "current_period_start": now.isoformat(),
                "current_period_end": (now + timedelta(days=31)).isoformat(),
            }
        ).execute()
    except APIError:
        pass


def _count_generation_usage(supabase: Client, *, user_id: str, period: str) -> int:
    try:
        logs = (
            supabase.table("usage_logs")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("action", "generate_video")
            .gte("created_at", period)
            .execute()
        )
        return logs.count or 0
    except APIError:
        return 0


def _sync_user_quota(
    supabase: Client,
    *,
    user_id: str,
    plan: str,
    quota: int | None,
    used: int,
) -> None:
    if quota is None:
        return
    reset_month = current_reset_month()
    payload = {
        "user_id": user_id,
        "plan": plan,
        "monthly_limit": quota,
        "used_count": used,
        "remaining_count": max(quota - used, 0),
        "reset_month": reset_month,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    try:
        existing = (
            supabase.table("user_quotas")
            .select("id")
            .eq("user_id", user_id)
            .eq("reset_month", reset_month)
            .limit(1)
            .execute()
        )
        if existing.data:
            supabase.table("user_quotas").update(payload).eq("id", existing.data[0]["id"]).execute()
        else:
            supabase.table("user_quotas").insert(payload).execute()
    except APIError:
        pass


def _get_user_quota(supabase: Client, *, user_id: str) -> dict[str, Any] | None:
    try:
        result = (
            supabase.table("user_quotas")
            .select("*")
            .eq("user_id", user_id)
            .eq("reset_month", current_reset_month())
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except APIError:
        return None


def _quota_for_user(supabase: Client, *, user_id: str) -> tuple[str, int | None]:
    try:
        result = (
            supabase.table("profiles")
            .select("plan,monthly_quota,custom_quota")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if result.data:
            profile = result.data[0]
            plan = profile.get("plan") or FREE_PLAN
            quota = profile.get("custom_quota")
            if quota is None:
                quota = profile.get("monthly_quota")
            if quota is None:
                quota = PLAN_QUOTAS.get(plan, FREE_MONTHLY_QUOTA)
            return plan, quota
    except APIError:
        pass
    return FREE_PLAN, FREE_MONTHLY_QUOTA


def _default_plan_row(code: str) -> dict[str, Any]:
    return next((plan for plan in DEFAULT_PLAN_ROWS if plan["code"] == code), DEFAULT_PLAN_ROWS[0]).copy()


def _get_plan_row(supabase: Client, code: str) -> dict[str, Any]:
    try:
        result = supabase.table("plans").select("*").eq("code", code).limit(1).execute()
        if result.data:
            return {**_default_plan_row(code), **result.data[0]}
    except APIError:
        pass
    return _default_plan_row(code)


def list_admin_plans(supabase: Client) -> list[dict[str, Any]]:
    try:
        result = supabase.table("plans").select("*").order("sort_order").execute()
        if result.data:
            return result.data
    except APIError:
        pass
    return [plan.copy() for plan in DEFAULT_PLAN_ROWS]


def update_plan_admin(
    supabase: Client,
    *,
    code: str,
    name: str | None = None,
    description: str | None = None,
    monthly_quota: int | None = None,
    monthly_quota_unlimited: bool = False,
    monthly_price_cny: int | None = None,
    yearly_price_cny: int | None = None,
    voice_clone_enabled: bool | None = None,
    is_active: bool | None = None,
    sort_order: int | None = None,
) -> dict[str, Any]:
    if code not in PLAN_QUOTAS:
        raise HTTPException(status_code=400, detail="Invalid plan code")
    payload: dict[str, Any] = {"code": code, "updated_at": datetime.now(UTC).isoformat()}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if monthly_quota_unlimited:
        payload["monthly_quota"] = None
    elif monthly_quota is not None:
        payload["monthly_quota"] = monthly_quota
    if monthly_price_cny is not None:
        payload["monthly_price_cny"] = monthly_price_cny
    if yearly_price_cny is not None:
        payload["yearly_price_cny"] = yearly_price_cny
    if voice_clone_enabled is not None:
        payload["voice_clone_enabled"] = voice_clone_enabled
    if is_active is not None:
        payload["is_active"] = is_active
    if sort_order is not None:
        payload["sort_order"] = sort_order
    existing = _get_plan_row(supabase, code)
    upsert_payload = {**existing, **payload}
    result = supabase.table("plans").upsert(upsert_payload, on_conflict="code").execute()
    return result.data[0]


def get_usage_summary(supabase: Client, *, user_id: str, email: str) -> dict[str, Any]:
    profile = ensure_profile(supabase, user_id=user_id, email=email)
    if profile.get("status") == "banned":
        raise HTTPException(status_code=403, detail="账户已被禁用，请联系管理员。")
    plan = profile.get("plan") or "free"
    quota = profile.get("custom_quota")
    if quota is None:
        quota = profile.get("monthly_quota")
    if quota is None and plan in PLAN_QUOTAS:
        quota = _get_plan_row(supabase, plan).get("monthly_quota")

    period = current_period_start()
    quota_record = _get_user_quota(supabase, user_id=user_id)
    if quota_record:
        plan = quota_record.get("plan") or plan
        quota = quota_record.get("monthly_limit")
        used = int(quota_record.get("used_count") or 0)
        remaining = int(quota_record.get("remaining_count") or 0)
    else:
        used = _count_generation_usage(supabase, user_id=user_id, period=period)
        remaining = None if quota is None else max(int(quota) - used, 0)
        _sync_user_quota(supabase, user_id=user_id, plan=plan, quota=quota, used=used)

    return {
        "plan": plan,
        "monthly_quota": quota,
        "used": used,
        "remaining": remaining,
        "period_start": period,
        "voice_clone_enabled": bool(profile.get("voice_clone_enabled")) or bool(_get_plan_row(supabase, plan).get("voice_clone_enabled")),
        "default_voice_id": profile.get("default_voice_id"),
    }


def get_generation_limits(supabase: Client, *, user_id: str, email: str) -> dict[str, Any]:
    usage = get_usage_summary(supabase, user_id=user_id, email=email)
    plan = usage["plan"]
    return {
        "plan": plan,
        "max_seconds": 15 if plan == "free" else 90 if plan in {"pro", "business"} else 45,
        "watermark": plan == "free",
        "voice_clone_enabled": usage.get("voice_clone_enabled", False),
    }


def assert_voice_clone_allowed(supabase: Client, *, user_id: str, email: str) -> dict[str, Any]:
    usage = get_usage_summary(supabase, user_id=user_id, email=email)
    if not usage.get("voice_clone_enabled"):
        raise HTTPException(status_code=403, detail="声音克隆仅 Pro / Business 用户可用，请升级到 Pro。")
    return usage


def assert_generation_quota(supabase: Client, *, user_id: str, email: str) -> dict[str, Any]:
    usage = get_usage_summary(supabase, user_id=user_id, email=email)
    if usage["remaining"] is not None and usage["remaining"] <= 0:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "insufficient_credits",
                "message": "免费额度已用完，请升级套餐。",
                "plan": usage["plan"],
                "remaining": usage["remaining"],
                "monthly_quota": usage["monthly_quota"],
            },
        )
    return usage


def log_generation_usage(
    supabase: Client,
    *,
    user_id: str,
    task_id: str | None = None,
    avatar_task_id: str | None = None,
) -> None:
    inserted = False
    payload = {
        "user_id": user_id,
        "action": "generate_video",
        "quantity": 1,
        "period_start": current_period_start(),
    }
    if task_id:
        payload["task_id"] = task_id
    if avatar_task_id:
        payload["avatar_task_id"] = avatar_task_id
    try:
        supabase.table("usage_logs").insert(payload).execute()
    except APIError:
        try:
            fallback_payload = {key: value for key, value in payload.items() if key not in {"task_id", "avatar_task_id"}}
            supabase.table("usage_logs").insert(fallback_payload).execute()
        except APIError:
            return
        inserted = True
    else:
        inserted = True
    if not inserted:
        return
    period = current_period_start()
    used = _count_generation_usage(supabase, user_id=user_id, period=period)
    plan, quota = _quota_for_user(supabase, user_id=user_id)
    _sync_user_quota(supabase, user_id=user_id, plan=plan, quota=quota, used=used)
    if quota is not None:
        try:
            supabase.table("profiles").update(
                {"credits": max(int(quota) - used, 0), "updated_at": datetime.now(UTC).isoformat()}
            ).eq("id", user_id).execute()
        except APIError:
            pass


def refund_generation_usage(supabase: Client, *, user_id: str, task_id: str) -> None:
    try:
        usage = (
            supabase.table("usage_logs")
            .select("id")
            .eq("user_id", user_id)
            .eq("task_id", task_id)
            .eq("action", "generate_video")
            .limit(1)
            .execute()
        )
        if usage.data:
            supabase.table("usage_logs").delete().eq("id", usage.data[0]["id"]).execute()
            used = _count_generation_usage(supabase, user_id=user_id, period=current_period_start())
            plan, quota = _quota_for_user(supabase, user_id=user_id)
            _sync_user_quota(supabase, user_id=user_id, plan=plan, quota=quota, used=used)
    except Exception:
        pass


def list_user_orders(supabase: Client, *, user_id: str) -> list[dict[str, Any]]:
    try:
        result = (
            supabase.table("orders")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data
    except APIError:
        return []


def list_user_usage_logs(supabase: Client, *, user_id: str) -> list[dict[str, Any]]:
    try:
        result = (
            supabase.table("usage_logs")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return result.data
    except APIError:
        return []


def list_admin_users(supabase: Client) -> list[dict[str, Any]]:
    result = supabase.table("profiles").select("*").order("created_at", desc=True).execute()
    users = result.data
    if not users:
        return users

    clone_counts: dict[str, int] = {}
    try:
        clone_result = supabase.table("voice_clones").select("user_id").execute()
        for clone in clone_result.data or []:
            user_id = clone.get("user_id")
            if user_id:
                clone_counts[user_id] = clone_counts.get(user_id, 0) + 1
    except Exception:
        clone_counts = {}

    for user in users:
        user["voice_clone_count"] = clone_counts.get(user["id"], 0)
    return users


def list_admin_orders(supabase: Client) -> list[dict[str, Any]]:
    result = supabase.table("orders").select("*").order("created_at", desc=True).limit(200).execute()
    return result.data


def list_admin_subscriptions(supabase: Client) -> list[dict[str, Any]]:
    result = supabase.table("subscriptions").select("*").order("created_at", desc=True).limit(200).execute()
    return result.data


def list_admin_payments(supabase: Client) -> list[dict[str, Any]]:
    result = supabase.table("payments").select("*").order("created_at", desc=True).limit(200).execute()
    return result.data


def list_admin_quotas(supabase: Client) -> list[dict[str, Any]]:
    result = supabase.table("user_quotas").select("*").order("updated_at", desc=True).limit(500).execute()
    quotas = result.data
    if not quotas:
        return quotas
    user_ids = sorted({quota["user_id"] for quota in quotas if quota.get("user_id")})
    email_by_user: dict[str, str] = {}
    if user_ids:
        try:
            profiles = supabase.table("profiles").select("id,email").in_("id", user_ids).execute()
            email_by_user = {profile["id"]: profile.get("email", "") for profile in profiles.data or []}
        except APIError:
            email_by_user = {}
    for quota in quotas:
        quota["email"] = email_by_user.get(quota.get("user_id"), "")
    return quotas


def update_quota_admin(
    supabase: Client,
    *,
    quota_id: str,
    monthly_limit: int | None = None,
    used_count: int | None = None,
    remaining_count: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"updated_at": datetime.now(UTC).isoformat()}
    if monthly_limit is not None:
        payload["monthly_limit"] = monthly_limit
    if used_count is not None:
        payload["used_count"] = used_count
    if remaining_count is not None:
        payload["remaining_count"] = remaining_count
    result = supabase.table("user_quotas").update(payload).eq("id", quota_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Quota not found")
    return result.data[0]


def update_profile_admin(
    supabase: Client,
    *,
    user_id: str,
    plan: str | None = None,
    monthly_quota: int | None = None,
    custom_quota: int | None = None,
    voice_clone_enabled: bool | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"updated_at": datetime.now(UTC).isoformat()}
    if plan:
        payload["plan"] = plan
        plan_row = _get_plan_row(supabase, plan)
        payload["monthly_quota"] = plan_row.get("monthly_quota")
        payload["voice_clone_enabled"] = bool(plan_row.get("voice_clone_enabled"))
    if monthly_quota is not None:
        payload["monthly_quota"] = monthly_quota
    if custom_quota is not None:
        payload["custom_quota"] = custom_quota
    if voice_clone_enabled is not None:
        payload["voice_clone_enabled"] = voice_clone_enabled
    if status:
        payload["status"] = status
    result = supabase.table("profiles").update(payload).eq("id", user_id).execute()
    return result.data[0]


def mark_order_paid_and_upgrade(supabase: Client, *, order_id: str, provider_payment_id: str = "") -> dict[str, Any]:
    order_result = supabase.table("orders").select("*").eq("id", order_id).limit(1).execute()
    if not order_result.data:
        raise HTTPException(status_code=404, detail="Order not found")
    order = order_result.data[0]
    now = datetime.now(UTC)
    plan = order["plan"]
    plan_row = _get_plan_row(supabase, plan)
    quota = plan_row.get("monthly_quota")

    supabase.table("orders").update(
        {"status": "paid", "updated_at": now.isoformat()}
    ).eq("id", order_id).execute()
    supabase.table("payments").insert(
        {
            "order_id": order_id,
            "user_id": order["user_id"],
            "provider": order["provider"],
            "status": "paid",
            "provider_payment_id": provider_payment_id,
            "amount": order["amount"],
            "currency": order["currency"],
        }
    ).execute()
    supabase.table("profiles").update(
        {
            "plan": plan,
            "monthly_quota": quota,
            "voice_clone_enabled": bool(plan_row.get("voice_clone_enabled")),
            "custom_quota": None,
            "status": "active",
            "updated_at": now.isoformat(),
        }
    ).eq("id", order["user_id"]).execute()
    supabase.table("subscriptions").insert(
        {
            "user_id": order["user_id"],
            "plan": plan,
            "status": "active",
            "provider": order["provider"],
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=366 if order.get("billing_cycle") == "yearly" else 31)).isoformat(),
        }
    ).execute()
    return order


def create_order(
    supabase: Client,
    *,
    user_id: str,
    plan: str,
    provider: str,
    currency: str,
    billing_cycle: str,
) -> dict[str, Any]:
    amount = PLAN_PRICES.get(plan, {}).get(billing_cycle, {}).get(currency, 0)
    if currency == "CNY":
        plan_row = _get_plan_row(supabase, plan)
        amount = int(plan_row.get("yearly_price_cny" if billing_cycle == "yearly" else "monthly_price_cny") or amount)
    result = supabase.table("orders").insert(
        {
            "user_id": user_id,
            "plan": plan,
            "currency": currency,
            "amount": amount,
            "provider": provider,
            "status": "pending",
            "billing_cycle": billing_cycle,
            "metadata": {"checkout": "pending"},
        }
    ).execute()
    return result.data[0]


async def create_checkout_session(order: dict[str, Any]) -> dict[str, Any]:
    provider = order["provider"]
    if provider == "stripe":
        return await _create_stripe_checkout(order)
    if provider == "paypal":
        return await _create_paypal_order(order)
    if provider == "lemon_squeezy":
        return _missing_provider_config("lemon_squeezy", order)
    if provider == "creem":
        return _missing_provider_config("creem", order)
    if provider in {"wechat", "alipay", "pingpp"}:
        return await _create_pingpp_charge(order)
    if provider == "manual":
        return {
            "checkout_url": None,
            "provider_status": "manual_review",
            "message": "已创建人工审核订单，管理员可在后台标记为已支付。",
        }
    raise HTTPException(status_code=400, detail="Unsupported payment provider.")


async def _create_stripe_checkout(order: dict[str, Any]) -> dict[str, Any]:
    if not settings.stripe_secret_key:
        return _missing_provider_config("stripe", order)
    price_name = f"kaiqiang.ai {order['plan']} {order.get('billing_cycle', 'monthly')}"
    payload = {
        "mode": "payment",
        "success_url": f"{settings.public_site_url}/account?payment=success&order_id={order['id']}",
        "cancel_url": f"{settings.public_site_url}/pricing?payment=cancelled",
        "client_reference_id": order["id"],
        "metadata[order_id]": order["id"],
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": order["currency"].lower(),
        "line_items[0][price_data][product_data][name]": price_name,
        "line_items[0][price_data][unit_amount]": str(order["amount"]),
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=payload,
            auth=(settings.stripe_secret_key, ""),
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Stripe checkout failed: {response.text}")
    data = response.json()
    return {"checkout_url": data.get("url"), "provider_status": "created", "provider_payload": data}


async def _create_paypal_order(order: dict[str, Any]) -> dict[str, Any]:
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        return _missing_provider_config("paypal", order)
    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(
            f"{settings.paypal_api_base}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(settings.paypal_client_id, settings.paypal_client_secret),
        )
        if token_response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"PayPal token failed: {token_response.text}")
        token = token_response.json()["access_token"]
        order_response = await client.post(
            f"{settings.paypal_api_base}/v2/checkout/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": order["id"],
                        "amount": {
                            "currency_code": order["currency"],
                            "value": f"{order['amount'] / 100:.2f}",
                        },
                    }
                ],
                "application_context": {
                    "return_url": f"{settings.public_site_url}/account?payment=success&order_id={order['id']}",
                    "cancel_url": f"{settings.public_site_url}/pricing?payment=cancelled",
                },
            },
        )
    if order_response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"PayPal order failed: {order_response.text}")
    data = order_response.json()
    checkout_url = next((link["href"] for link in data.get("links", []) if link.get("rel") == "approve"), None)
    return {"checkout_url": checkout_url, "provider_status": "created", "provider_payload": data}


async def _create_pingpp_charge(order: dict[str, Any]) -> dict[str, Any]:
    if not settings.pingpp_api_key or not settings.pingpp_app_id:
        return _missing_provider_config("pingpp", order)
    channel = "wx_pub_qr" if order["provider"] == "wechat" else "alipay_qr"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://api.pingxx.com/v1/charges",
            auth=(settings.pingpp_api_key, ""),
            json={
                "order_no": order["id"],
                "app": {"id": settings.pingpp_app_id},
                "channel": channel,
                "amount": order["amount"],
                "client_ip": "127.0.0.1",
                "currency": order["currency"].lower(),
                "subject": f"kaiqiang.ai {order['plan']}",
                "body": f"{order['plan']} {order.get('billing_cycle', 'monthly')}",
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Ping++ charge failed: {response.text}")
    data = response.json()
    credential = data.get("credential", {})
    checkout_url = credential.get("alipay_qr") or credential.get("wx_pub_qr")
    return {"checkout_url": checkout_url, "provider_status": "created", "provider_payload": data}


def _missing_provider_config(provider: str, order: dict[str, Any]) -> dict[str, Any]:
    return {
        "checkout_url": None,
        "provider_status": "not_configured",
        "message": "支付系统即将开放，订单已保留为 pending。",
        "provider_payload": {"order_id": order["id"]},
    }
