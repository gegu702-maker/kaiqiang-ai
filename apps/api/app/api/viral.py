import asyncio

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.video_link_resolver import resolve_video_link
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
    industry: str = "personal_brand"
    language: str = "zh"


def _is_pipeline_tester(email: str | None) -> bool:
    if not email:
        return False
    allowed = {item.strip().lower() for item in settings.viral_pipeline_allowed_emails.split(",") if item.strip()}
    return email.lower() in allowed


@router.post("/link/resolve")
async def resolve_viral_link(
    payload: ViralLinkResolveRequest,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    get_authenticated_user(supabase, token)
    try:
        return await asyncio.wait_for(resolve_video_link(payload.source_url), timeout=min(settings.viral_pipeline_timeout_seconds, 45))
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "platform": "douyin",
            "title": "",
            "description": "",
            "duration": 0,
            "thumbnail": "",
            "webpage_url": "",
            "downloadable": False,
            "fallback_reason": "链接解析超时，请稍后重试，或上传视频/粘贴文案继续。",
            "error_code": "resolver_timeout",
            "errorCode": "resolver_timeout",
            "input_url": payload.source_url,
            "inputUrl": payload.source_url,
            "fallback_actions": ["upload_video", "paste_script", "check_link"],
            "fallbackActions": ["upload_video", "paste_script", "check_link"],
        }


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
            "status": "failed",
            "failed_at": "pending",
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
            ),
            timeout=settings.viral_pipeline_timeout_seconds,
        )
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "status": "failed",
            "failed_at": "transcribing",
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
