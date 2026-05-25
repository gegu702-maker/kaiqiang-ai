from supabase import Client, create_client
from fastapi import HTTPException

from app.core.config import settings


def get_supabase() -> Client:
    if not settings.supabase_url or settings.supabase_url == "https://example.supabase.co":
        raise HTTPException(status_code=500, detail="SUPABASE_URL is not configured on the API server.")
    if not settings.supabase_service_role_key:
        raise HTTPException(status_code=500, detail="SUPABASE_SERVICE_ROLE_KEY is not configured on the API server.")
    try:
        return create_client(settings.supabase_url, settings.supabase_service_role_key)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Supabase client initialization failed: {error}") from error
