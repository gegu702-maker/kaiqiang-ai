import asyncio

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.video_link_resolver import check_video_link, resolve_video_link
from app.services.viral_analyzer import analyze_viral_script
from app.services.viral_pipeline import run_viral_pipeline

router = APIRouter(prefix="/viral", tags=["viral"])


class ViralAnalyzeRequest(BaseModel):
    source_url: str = Field(default="", max_length=2000)
    raw_script: str = Field(default="", max_length=6000)
    industry: str
    language: str = "zh"


class ViralLinkResolveRequest(BaseModel):
    source_url: str = Field(..., min_length=1, max_length=3000)


class ViralPipelineRequest(BaseModel):
    source_url: str = Field(..., min_length=1, max_length=3000)
    raw_input: str = Field(default="", max_length=6000)
    industry: str = "personal_brand"
    language: str = "zh"


def _is_pipeline_tester(email: str | None) -> bool:
    if not email:
        return False
    allowed = {item.strip().lower() for item in settings.viral_pipeline_allowed_emails.split(",") if item.strip()}
    return not allowed or email.lower() in allowed


@router.post("/link/resolve")
async def resolve_viral_link(
    payload: ViralLinkResolveRequest,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    get_authenticated_user(supabase, token)
    return await resolve_video_link(payload.source_url)


@router.post("/link/check")
async def check_viral_link(
    payload: ViralLinkResolveRequest,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    get_authenticated_user(supabase, token)
    return await check_video_link(payload.source_url)


@router.post("/pipeline/run")
async def run_viral_agent_pipeline(
    payload: ViralPipelineRequest,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    if not _is_pipeline_tester(user.get("email")):
        return {
            "ok": False,
            "success": False,
            "status": "failed",
            "failed_at": "pending",
            "error_code": "unknown_error",
            "message": "自动解析内测中，请上传视频或粘贴文案继续分析。",
            "fallback_available": True,
            "fallback_options": ["upload_video", "paste_text"],
            "fallback_reason": "自动解析内测中，请上传视频或粘贴文案继续分析。",
            "project_id": "",
            "transcript": "",
            "analysis": None,
            "rewrites": [],
            "metadata": {},
        }
    try:
        return await asyncio.wait_for(
            run_viral_pipeline(
                supabase,
                user_id=user["id"],
                email=user["email"],
                source_url=payload.source_url,
                industry=payload.industry,
                language=payload.language,
                raw_input=payload.raw_input,
            ),
            timeout=settings.viral_pipeline_timeout_seconds,
        )
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "success": False,
            "status": "failed",
            "failed_at": "transcribing",
            "error_code": "resolver_timeout",
            "message": "链接检查超时，请稍后重试，或使用上传/粘贴方式。",
            "fallback_available": True,
            "fallback_options": ["upload_video", "paste_text"],
            "fallback_reason": "自动解析超时，请上传视频继续分析。",
            "project_id": "",
            "transcript": "",
            "analysis": None,
            "rewrites": [],
            "metadata": {},
        }


@router.post("/analyze")
async def analyze_viral(
    payload: ViralAnalyzeRequest,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    return await analyze_viral_script(
        supabase,
        user_id=user["id"],
        email=user["email"],
        source_url=payload.source_url,
        raw_script=payload.raw_script,
        industry=payload.industry,
        language=payload.language,
    )
