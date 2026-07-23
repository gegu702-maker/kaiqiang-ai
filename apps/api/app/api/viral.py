import asyncio
import logging

from typing import Any, Literal

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, File, Form, UploadFile
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.video_link_resolver import check_video_link, resolve_video_link
from app.services.viral_analyzer import analyze_viral_script
from app.services.viral_pipeline import continue_reviewed_viral_pipeline, run_uploaded_viral_pipeline, run_viral_pipeline
from app.services.viral_diagnostics import bind_request_id, new_request_id, reset_request_id

router = APIRouter(prefix="/viral", tags=["viral"])
logger = logging.getLogger(__name__)


class ViralAnalyzeRequest(BaseModel):
    source_url: str = Field(default="", max_length=2000)
    raw_script: str = Field(default="", max_length=120000)
    industry: str
    language: str = "zh"
    rewrite_length: Literal["short", "medium", "full"] = "short"


class ViralLinkResolveRequest(BaseModel):
    source_url: str = Field(..., min_length=1, max_length=3000)


class ViralPipelineRequest(BaseModel):
    source_url: str = Field(..., min_length=1, max_length=3000)
    raw_input: str = Field(default="", max_length=6000)
    industry: str = "personal_brand"
    language: str = "zh"
    rewrite_length: Literal["short", "medium", "full"] = "short"


class ViralReviewContinueRequest(BaseModel):
    review_context: dict[str, Any]
    review_token: str = Field(..., min_length=1, max_length=256)
    confirmed_segments: list[dict[str, Any]]
    source_url: str = Field(default="", max_length=3000)
    industry: str = "personal_brand"
    language: str = "zh"
    rewrite_length: Literal["short", "medium", "full"] = "full"


def _is_pipeline_tester(email: str | None) -> bool:
    if not email:
        return False
    allowed = {item.strip().lower() for item in settings.viral_pipeline_allowed_emails.split(",") if item.strip()}
    return not allowed or email.lower() in allowed


def _pipeline_failure(*, request_id: str, code: str, stage: str, message: str, retryable: bool) -> dict:
    return {
        "ok": False,
        "success": False,
        "status": "failed",
        "failed_at": stage,
        "error_code": code,
        "code": code,
        "stage": stage,
        "message": message,
        "retryable": retryable,
        "request_id": request_id,
        "fallback_available": True,
        "fallback_options": ["upload_video", "paste_text"],
        "fallback_reason": message,
        "project_id": "",
        "transcript": "",
        "analysis": None,
        "rewrites": [],
        "metadata": {},
    }


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
    request_id = new_request_id()
    context_token = bind_request_id(request_id)
    user = get_authenticated_user(supabase, token)
    if not _is_pipeline_tester(user.get("email")):
        reset_request_id(context_token)
        return _pipeline_failure(
            request_id=request_id,
            code="tester_not_allowed",
            stage="pending",
            message="自动解析内测中，请上传视频或粘贴文案继续分析。",
            retryable=False,
        )
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
                rewrite_length=payload.rewrite_length,
            ),
            timeout=settings.viral_pipeline_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning("viral_pipeline request_id=%s stage=pipeline outcome=timeout", request_id)
        return _pipeline_failure(
            request_id=request_id,
            code="pipeline_timeout",
            stage="analyzing",
            message="链接拆解处理超时。",
            retryable=True,
        )
    except Exception as error:
        logger.exception("viral_pipeline request_id=%s stage=pipeline outcome=unexpected_failure", request_id)
        return _pipeline_failure(
            request_id=request_id,
            code="pipeline_unexpected_error",
            stage="analyzing",
            message=f"拆解流程发生未预期错误（{type(error).__name__}）。",
            retryable=True,
        )
    finally:
        reset_request_id(context_token)


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
        rewrite_length=payload.rewrite_length,
    )


@router.post("/pipeline/upload")
async def run_uploaded_viral_agent_pipeline(
    video_file: UploadFile = File(...),
    source_url: str = Form(default=""),
    industry: str = Form(default="personal_brand"),
    language: str = Form(default="zh"),
    rewrite_length: Literal["short", "medium", "full"] = Form(default="short"),
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    request_id = new_request_id()
    context_token = bind_request_id(request_id)
    user = get_authenticated_user(supabase, token)
    try:
        return await asyncio.wait_for(
            run_uploaded_viral_pipeline(
                supabase,
                upload=video_file,
                user_id=user["id"],
                email=user["email"],
                source_url=source_url,
                industry=industry,
                language=language,
                rewrite_length=rewrite_length,
            ),
            timeout=settings.viral_pipeline_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning("viral_pipeline request_id=%s stage=upload_pipeline outcome=timeout", request_id)
        result = _pipeline_failure(
            request_id=request_id,
            code="pipeline_timeout",
            stage="transcribing",
            message="上传视频分析超时，未静默降级。",
            retryable=True,
        )
        result.update({"fallback_options": ["paste_text"], "source_type": "uploaded_video_asr", "degraded": False})
        return result
    except Exception as error:
        logger.exception("viral_pipeline request_id=%s stage=upload_pipeline outcome=unexpected_failure", request_id)
        result = _pipeline_failure(
            request_id=request_id,
            code="pipeline_unexpected_error",
            stage="processing",
            message=f"上传视频处理发生未预期错误（{type(error).__name__}）。",
            retryable=True,
        )
        result.update({"fallback_options": ["paste_text"], "source_type": "uploaded_video_asr", "degraded": False})
        return result
    finally:
        reset_request_id(context_token)


@router.post("/pipeline/continue")
async def continue_reviewed_viral_agent_pipeline(
    payload: ViralReviewContinueRequest,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    request_id = new_request_id()
    context_token = bind_request_id(request_id)
    user = get_authenticated_user(supabase, token)
    try:
        return await asyncio.wait_for(
            continue_reviewed_viral_pipeline(
                supabase,
                user_id=user["id"],
                email=user["email"],
                review_context=payload.review_context,
                review_token=payload.review_token,
                confirmed_segments=payload.confirmed_segments,
                source_url=payload.source_url,
                industry=payload.industry,
                language=payload.language,
                rewrite_length=payload.rewrite_length,
            ),
            timeout=settings.viral_pipeline_timeout_seconds,
        )
    except asyncio.TimeoutError:
        return _pipeline_failure(
            request_id=request_id,
            code="pipeline_timeout",
            stage="analyzing",
            message="人工确认后的拆解处理超时。",
            retryable=True,
        )
    except Exception as error:
        logger.exception("viral_pipeline request_id=%s stage=review_continue outcome=unexpected_failure", request_id)
        return _pipeline_failure(
            request_id=request_id,
            code="pipeline_unexpected_error",
            stage="analyzing",
            message=f"确认后的拆解发生未预期错误（{type(error).__name__}）。",
            retryable=True,
        )
    finally:
        reset_request_id(context_token)
