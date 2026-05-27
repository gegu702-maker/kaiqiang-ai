from pathlib import Path
from time import sleep
from uuid import uuid4
import logging

from fastapi import HTTPException, UploadFile
from supabase import Client

logger = logging.getLogger(__name__)


def ensure_public_bucket(supabase: Client, bucket: str) -> None:
    try:
        existing = {item.name for item in supabase.storage.list_buckets()}
    except Exception:
        logger.exception("Supabase bucket check failed for bucket=%s", bucket)
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
    allowed_format_label: str | None = None,
) -> str:
    filename = upload.filename or "upload"
    content_type = upload.content_type or "application/octet-stream"
    extension = Path(filename).suffix.lower() or _extension_from_content_type(content_type)
    allowed_label = allowed_format_label or ", ".join(sorted(item.lstrip(".") for item in allowed_extensions))
    current_format = extension.lstrip(".") or content_type or "unknown"
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"当前文件格式：{current_format}；支持格式：{allowed_label}",
        )

    if content_type not in allowed_content_types:
        raise HTTPException(
            status_code=400,
            detail=f"当前文件类型：{content_type}；支持格式：{allowed_label}",
        )

    object_path = f"{folder}/{uuid4().hex}{extension}"
    content = await upload.read()
    if len(content) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File is too large. Max size is {max_mb}MB")

    _with_retries(
        lambda: supabase.storage.from_(bucket).upload(
            object_path,
            content,
            {"content-type": _content_type_for_storage(extension, content_type)},
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


def _extension_from_content_type(content_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/wave": ".wav",
        "audio/m4a": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/mp4": ".m4a",
        "video/mp4": ".m4a",
    }.get(content_type, "")


def _content_type_for_storage(extension: str, content_type: str) -> str:
    if content_type != "application/octet-stream":
        return content_type
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".mpeg": "audio/mpeg",
    }.get(extension, content_type)
