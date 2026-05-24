from fastapi import APIRouter, Depends, Form, HTTPException, Request
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.supabase import get_supabase
from app.services.billing import (
    create_checkout_session,
    create_order,
    get_usage_summary,
    list_user_orders,
    list_user_usage_logs,
    mark_order_paid_and_upgrade,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/usage")
def get_current_usage(
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    return get_usage_summary(supabase, user_id=user["id"], email=user["email"])


@router.post("/orders")
async def create_checkout_order(
    plan: str = Form(...),
    provider: str = Form(default="manual"),
    currency: str = Form(default="CNY"),
    billing_cycle: str = Form(default="monthly"),
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    if plan not in {"plus", "pro", "business"}:
        raise HTTPException(status_code=400, detail="Only paid plans can create checkout orders.")
    if provider not in {"wechat", "alipay", "pingpp", "stripe", "paypal", "manual"}:
        raise HTTPException(status_code=400, detail="Unsupported payment provider.")
    if currency not in {"CNY", "USD"}:
        raise HTTPException(status_code=400, detail="Unsupported currency.")
    if billing_cycle not in {"monthly", "yearly"}:
        raise HTTPException(status_code=400, detail="Unsupported billing cycle.")

    order = create_order(
        supabase,
        user_id=user["id"],
        plan=plan,
        provider=provider,
        currency=currency,
        billing_cycle=billing_cycle,
    )
    checkout = await create_checkout_session(order)
    return {
        "order": order,
        "checkout_url": checkout.get("checkout_url"),
        "provider_status": checkout.get("provider_status", "pending"),
        "payment_status": "pending",
        "message": checkout.get("message", "订单已创建，请继续完成支付。"),
    }


@router.get("/orders")
def get_my_orders(
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    user = get_authenticated_user(supabase, token)
    return list_user_orders(supabase, user_id=user["id"])


@router.get("/usage-logs")
def get_my_usage_logs(
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    user = get_authenticated_user(supabase, token)
    return list_user_usage_logs(supabase, user_id=user["id"])


@router.post("/webhooks/{provider}")
async def payment_webhook(
    provider: str,
    request: Request,
    supabase: Client = Depends(get_supabase),
) -> dict:
    payload = await request.json()
    order_id = None
    provider_payment_id = ""

    if provider == "stripe":
        event_type = payload.get("type")
        data_object = payload.get("data", {}).get("object", {})
        if event_type == "checkout.session.completed":
            order_id = data_object.get("metadata", {}).get("order_id") or data_object.get("client_reference_id")
            provider_payment_id = data_object.get("payment_intent") or data_object.get("id", "")
    elif provider == "paypal":
        resource = payload.get("resource", {})
        units = resource.get("purchase_units") or []
        if units:
            order_id = units[0].get("reference_id")
        provider_payment_id = resource.get("id", "")
    elif provider in {"pingpp", "wechat", "alipay"}:
        order_id = payload.get("order_no") or payload.get("data", {}).get("object", {}).get("order_no")
        provider_payment_id = payload.get("id") or payload.get("data", {}).get("object", {}).get("id", "")

    if not order_id:
        raise HTTPException(status_code=400, detail="Webhook payload missing order id.")
    mark_order_paid_and_upgrade(supabase, order_id=order_id, provider_payment_id=provider_payment_id)
    return {"ok": True}
