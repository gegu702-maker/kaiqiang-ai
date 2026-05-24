from fastapi import APIRouter, Depends, Form, HTTPException
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.supabase import get_supabase
from app.services.billing import get_usage_summary

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/usage")
def get_current_usage(
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    return get_usage_summary(supabase, user_id=user["id"], email=user["email"])


@router.post("/orders")
def create_placeholder_order(
    plan: str = Form(...),
    provider: str = Form(default="manual"),
    currency: str = Form(default="CNY"),
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    if plan not in {"pro", "business"}:
        raise HTTPException(status_code=400, detail="Only paid plans can create placeholder orders.")
    if provider not in {"wechat", "alipay", "stripe", "paypal", "manual"}:
        raise HTTPException(status_code=400, detail="Unsupported payment provider.")

    amount_map = {"pro": 19900, "business": 0}
    result = supabase.table("orders").insert(
        {
            "user_id": user["id"],
            "plan": plan,
            "currency": currency,
            "amount": amount_map[plan],
            "provider": provider,
            "status": "pending",
            "metadata": {
                "mode": "placeholder",
                "message": "Payment provider is reserved for the SaaS MVP.",
            },
        }
    ).execute()
    return {
        "order": result.data[0],
        "payment_status": "pending",
        "message": "已创建支付占位订单，真实收款接口后续接入。",
    }
