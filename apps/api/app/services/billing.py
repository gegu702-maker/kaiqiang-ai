from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
import httpx
from supabase import Client

from app.core.config import settings

PLAN_QUOTAS: dict[str, int | None] = {
    "free": 3,
    "pro": 100,
    "business": None,
}

PLAN_PRICES: dict[str, dict[str, dict[str, int]]] = {
    "pro": {
        "monthly": {"CNY": 19900, "USD": 2900},
        "yearly": {"CNY": 199000, "USD": 29000},
    },
    "business": {
        "monthly": {"CNY": 0, "USD": 0},
        "yearly": {"CNY": 0, "USD": 0},
    },
}

PLAN_MONTHLY_QUOTAS = {
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
        profile = result.data[0]
        if profile.get("status") == "banned":
            raise HTTPException(status_code=403, detail="账户已被禁用，请联系管理员。")
        return profile

    payload = {
        "id": user_id,
        "email": email,
        "plan": "free",
        "monthly_quota": PLAN_QUOTAS["free"],
        "status": "active",
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


def list_user_orders(supabase: Client, *, user_id: str) -> list[dict[str, Any]]:
    result = (
        supabase.table("orders")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def list_user_usage_logs(supabase: Client, *, user_id: str) -> list[dict[str, Any]]:
    result = (
        supabase.table("usage_logs")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return result.data


def list_admin_users(supabase: Client) -> list[dict[str, Any]]:
    result = supabase.table("profiles").select("*").order("created_at", desc=True).execute()
    return result.data


def list_admin_orders(supabase: Client) -> list[dict[str, Any]]:
    result = supabase.table("orders").select("*").order("created_at", desc=True).limit(200).execute()
    return result.data


def update_profile_admin(
    supabase: Client,
    *,
    user_id: str,
    plan: str | None = None,
    monthly_quota: int | None = None,
    custom_quota: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"updated_at": datetime.now(UTC).isoformat()}
    if plan:
        payload["plan"] = plan
        payload["monthly_quota"] = PLAN_MONTHLY_QUOTAS.get(plan)
    if monthly_quota is not None:
        payload["monthly_quota"] = monthly_quota
    if custom_quota is not None:
        payload["custom_quota"] = custom_quota
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
    quota = PLAN_MONTHLY_QUOTAS.get(plan)

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
        "message": f"{provider} 环境变量未配置，订单已保留为 pending。",
        "provider_payload": {"order_id": order["id"]},
    }
