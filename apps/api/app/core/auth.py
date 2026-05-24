from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client


bearer_scheme = HTTPBearer(
    scheme_name="Supabase Bearer Token",
    description="Paste your Supabase access_token. Swagger will send it as Authorization: Bearer <token>.",
    auto_error=False,
)


def get_bearer_token(credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)) -> str:
    if not credentials or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=401, detail="请先登录后再生成视频。")
    return credentials.credentials.strip()


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
