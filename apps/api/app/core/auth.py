from fastapi import Header, HTTPException
from supabase import Client


def get_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="请先登录后再生成视频。")
    return authorization.split(" ", 1)[1].strip()


def get_authenticated_user(supabase: Client, token: str) -> dict:
    try:
        response = supabase.auth.get_user(token)
    except Exception as error:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录。") from error

    user = getattr(response, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录。")

    return {
        "id": str(user.id),
        "email": user.email,
    }
