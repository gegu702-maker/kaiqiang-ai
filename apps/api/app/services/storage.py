from pathlib import Path
from time import sleep
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from supabase import Client


def ensure_public_bucket(supabase: Client, bucket: str) -> None:
    try:
        existing = {item.name for item in supabase.storage.list_buckets()}
    except Exception:
        # Bucket checks are a convenience. If Supabase/proxy flakes here, let
        # the real upload decide rather than failing an already-generated voice.
        return
    if bucket not in existing:
        _with_retries(lambda: supabase.storage.create_bucket(bucket, options={"public": True}))


async def upload_public_file(
    supabase: Client,
    bucket: str,
    upload: UploadFile,
    folder: str,
    *,
    allowed_extensions: set[str],
    allowed_content_types: set[str],
    max_bytes: int,
) -> str:
    extension = Path(upload.filename or "upload").suffix.lower()
    if extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {extension}")

    if upload.content_type not in allowed_content_types:
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {upload.content_type}")

    object_path = f"{folder}/{uuid4().hex}{extension}"
    content = await upload.read()
    if len(content) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File is too large. Max size is {max_mb}MB")

    _with_retries(
        lambda: supabase.storage.from_(bucket).upload(
            object_path,
            content,
            {"content-type": upload.content_type or "application/octet-stream"},
        )
    )
    return supabase.storage.from_(bucket).get_public_url(object_path)


def upload_public_bytes(
    supabase: Client,
    bucket: str,
    content: bytes,
    folder: str,
    extension: str,
    content_type: str,
) -> str:
    object_path = f"{folder}/{uuid4().hex}{extension}"
    _with_retries(
        lambda: supabase.storage.from_(bucket).upload(
            object_path,
            content,
            {"content-type": content_type},
        )
    )
    return supabase.storage.from_(bucket).get_public_url(object_path)


def _with_retries(operation, attempts: int = 3):
    last_error: Exception | None = None
    for index in range(attempts):
        try:
            return operation()
        except Exception as error:
            last_error = error
            if index < attempts - 1:
                sleep(1.5 * (index + 1))
    raise last_error  # type: ignore[misc]
