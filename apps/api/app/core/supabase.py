import re

from fastapi import HTTPException
from supabase import Client, ClientOptions, create_client

from app.core.config import settings


_LEGACY_JWT_PATTERN = re.compile(
    r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$"
)


def _client_options_for_key(key: str) -> ClientOptions | None:
    if key.startswith("sb_secret_"):
        if len(key) == len("sb_secret_"):
            raise HTTPException(
                status_code=500,
                detail="SUPABASE_SERVICE_ROLE_KEY has an unsupported format.",
            )
        # Opaque API keys belong in the apikey header, not in a Bearer header.
        # supabase-py otherwise mirrors its API key into Authorization by default.
        return ClientOptions(headers={"Authorization": ""})
    if _LEGACY_JWT_PATTERN.fullmatch(key):
        return None
    raise HTTPException(
        status_code=500,
        detail="SUPABASE_SERVICE_ROLE_KEY has an unsupported format.",
    )


def get_supabase() -> Client:
    if not settings.supabase_url or settings.supabase_url == "https://example.supabase.co":
        raise HTTPException(status_code=500, detail="SUPABASE_URL is not configured on the API server.")
    key = settings.supabase_service_role_key.strip()
    if not key:
        raise HTTPException(status_code=500, detail="SUPABASE_SERVICE_ROLE_KEY is not configured on the API server.")
    try:
        options = _client_options_for_key(key)
        if options is not None:
            return create_client(settings.supabase_url, key, options)
        return create_client(settings.supabase_url, key)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail="Supabase client initialization failed.") from error
