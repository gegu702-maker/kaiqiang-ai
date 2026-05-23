import logging

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from supabase import Client

from app.core.config import settings
from app.core.supabase import get_supabase
from app.models.video_task import CosyVoiceCloneResponse, VideoTask
from app.services.cosyvoice import clone_voice_bytes
from app.services.storage import ensure_public_bucket, upload_public_bytes
from app.services.tasks import get_task, update_task

router = APIRouter(prefix="/cosyvoice", tags=["cosyvoice"])
logger = logging.getLogger(__name__)


def verify_admin(x_admin_key: str = Header(...)) -> None:
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


def try_update_task(supabase: Client, task_id: str, **kwargs) -> dict | None:
    try:
        return update_task(supabase, task_id, **kwargs)
    except Exception:
        return None


@router.post("/clone", response_model=CosyVoiceCloneResponse, dependencies=[Depends(verify_admin)])
async def clone_voice(
    text: str = Form(...),
    reference_audio: UploadFile = File(...),
    task_id: str | None = Form(default=None),
    prompt_text: str | None = Form(default=None),
    supabase: Client = Depends(get_supabase),
) -> CosyVoiceCloneResponse:
    final_text = text.strip()
    reference_text = (prompt_text or "").strip()
    logger.warning(
        "CosyVoice clone request task_id=%s reference_audio=%s final_text=%r prompt_text=%r",
        task_id,
        reference_audio.filename,
        final_text,
        reference_text,
    )
    print(
        "[CosyVoice clone request]",
        {
            "task_id": task_id,
            "reference_audio": reference_audio.filename,
            "final_text": final_text,
            "prompt_text": reference_text,
        },
        flush=True,
    )

    if task_id:
        task = get_task(supabase, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        try_update_task(supabase, task_id, cosyvoice_status="generating")

    try:
        audio_bytes, local_path, content_type = await clone_voice_bytes(
            text=final_text,
            reference_audio=reference_audio,
            prompt_text=reference_text,
        )
        extension = ".mp3" if "mpeg" in content_type or "mp3" in content_type else ".wav"
        ensure_public_bucket(supabase, settings.supabase_cloned_bucket)
        audio_url = upload_public_bytes(
            supabase,
            settings.supabase_cloned_bucket,
            audio_bytes,
            "voices",
            extension,
            content_type,
        )
    except Exception:
        if task_id:
            try_update_task(supabase, task_id, cosyvoice_status="failed")
        raise

    updated_task = None
    if task_id:
        updated_task = try_update_task(
            supabase,
            task_id,
            cloned_voice_url=audio_url,
            cosyvoice_status="completed",
        )
        if updated_task is None and task:
            updated_task = {
                **task,
                "cloned_voice_url": audio_url,
                "cosyvoice_status": "completed",
            }

    return CosyVoiceCloneResponse(
        audio_url=audio_url,
        local_path=local_path,
        cosyvoice_status="completed",
        task=VideoTask(**updated_task) if updated_task else None,
    )
