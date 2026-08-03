import asyncio
import hashlib
import json
import logging

from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.config import settings
from app.core.supabase import get_supabase
from app.services.video_link_resolver import check_video_link, resolve_video_link
from app.services.llm_provider import LLMProviderError
from app.services.viral_analyzer import analyze_viral_script
from app.services.viral_pipeline import run_uploaded_viral_pipeline, run_viral_pipeline
from app.services.viral_diagnostics import bind_request_id, new_request_id, reset_request_id
from app.services.viral_idempotency import (
    IdempotencyConflict,
    IdempotencyOutcome,
    viral_analysis_idempotency,
)

router = APIRouter(prefix="/viral", tags=["viral"])
logger = logging.getLogger(__name__)
_viral_upload_lock = asyncio.Lock()
LengthMode = Literal["match_source", "concise", "moderate_expand", "short", "medium", "full"]


class ViralAnalyzeRequest(BaseModel):
    source_url: str = Field(default="", max_length=2000)
    raw_script: str = Field(default="", max_length=120000)
    industry: str
    language: str = "zh"
    rewrite_length: LengthMode = "match_source"
    client_submission_id: str = Field(default="", max_length=96, pattern=r"^(|viral_submission_[0-9a-f]{32})$")


class ViralLinkResolveRequest(BaseModel):
    source_url: str = Field(..., min_length=1, max_length=3000)


class ViralPipelineRequest(BaseModel):
    source_url: str = Field(..., min_length=1, max_length=3000)
    raw_input: str = Field(default="", max_length=6000)
    industry: str = "personal_brand"
    language: str = "zh"
    rewrite_length: LengthMode = "match_source"


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


def _viral_analyze_fingerprint(payload: ViralAnalyzeRequest) -> str:
    canonical = json.dumps(
        {
            "source_url": payload.source_url,
            "raw_script": payload.raw_script,
            "industry": payload.industry,
            "language": payload.language,
            "rewrite_length": payload.rewrite_length,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _raise_idempotent_failure(outcome: IdempotencyOutcome) -> None:
    raise HTTPException(status_code=outcome.status_code, detail=outcome.payload)


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
    submission_id = payload.client_submission_id
    fingerprint = _viral_analyze_fingerprint(payload)
    claim = None
    if submission_id:
        try:
            claim = viral_analysis_idempotency.claim(
                user_id=user["id"],
                submission_id=submission_id,
                fingerprint=fingerprint,
            )
        except IdempotencyConflict as error:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_conflict",
                    "stage": "pending",
                    "message": str(error),
                    "retryable": False,
                    "client_submission_id": submission_id,
                },
            ) from error
        if not claim.is_owner:
            state = "completed" if claim.future.done() else "processing"
            logger.info(
                "viral_analyze_idempotency client_submission_id=%s fingerprint=%s state=%s outcome=reused",
                submission_id,
                fingerprint[:12],
                state,
            )
            outcome = await viral_analysis_idempotency.wait(claim)
            logger.info(
                "viral_analyze_idempotency request_id=%s client_submission_id=%s fingerprint=%s state=completed outcome=reused status=%s",
                outcome.payload.get("request_id", "unavailable"),
                submission_id,
                fingerprint[:12],
                outcome.status_code,
            )
            if outcome.status_code >= 400:
                _raise_idempotent_failure(outcome)
            return outcome.payload

    request_id = new_request_id()
    context_token = bind_request_id(request_id)
    try:
        logger.info(
            "viral_analyze_idempotency request_id=%s client_submission_id=%s fingerprint=%s state=processing outcome=owner",
            request_id,
            submission_id or "unavailable",
            fingerprint[:12],
        )
        result = await analyze_viral_script(
            supabase,
            user_id=user["id"],
            email=user["email"],
            source_url=payload.source_url,
            raw_script=payload.raw_script,
            industry=payload.industry,
            language=payload.language,
            rewrite_length=payload.rewrite_length,
        )
        actual_chars = result.get("diagnostic", {}).get("actual_chars", [])
        logger.info(
            "viral_analyze request_id=%s stage=ready outcome=completed actual_chars=%s",
            request_id,
            actual_chars,
        )
        response_payload = {
            **result,
            "request_id": request_id,
            "client_submission_id": submission_id or None,
        }
        if claim is not None:
            viral_analysis_idempotency.complete(
                user_id=user["id"],
                submission_id=submission_id,
                outcome=IdempotencyOutcome(status_code=200, payload=response_payload),
            )
        return response_payload
    except HTTPException as error:
        if isinstance(error.detail, dict):
            error.detail.setdefault("request_id", request_id)
            error.detail.setdefault("client_submission_id", submission_id or None)
        if claim is not None:
            failure_payload = (
                error.detail
                if isinstance(error.detail, dict)
                else {
                    "code": "analysis_http_error",
                    "stage": "analyzing",
                    "message": str(error.detail),
                    "request_id": request_id,
                    "client_submission_id": submission_id or None,
                }
            )
            viral_analysis_idempotency.complete(
                user_id=user["id"],
                submission_id=submission_id,
                outcome=IdempotencyOutcome(status_code=error.status_code, payload=failure_payload),
            )
        logger.warning(
            "viral_analyze request_id=%s stage=%s outcome=failed code=%s",
            request_id,
            error.detail.get("stage", "analyzing") if isinstance(error.detail, dict) else "analyzing",
            error.detail.get("code", "analysis_http_error") if isinstance(error.detail, dict) else "analysis_http_error",
        )
        raise
    except LLMProviderError as error:
        detail = {
            "code": "analysis_llm_provider_failed",
            "stage": "analyzing",
            "message": "模型响应未满足分析契约，已受控停止。",
            "retryable": bool(error.retryable),
            "request_id": request_id,
            "client_submission_id": submission_id or None,
            "failure_code": error.code,
        }
        if claim is not None:
            viral_analysis_idempotency.complete(
                user_id=user["id"],
                submission_id=submission_id,
                outcome=IdempotencyOutcome(status_code=502, payload=detail),
            )
        logger.warning(
            "viral_analyze request_id=%s stage=analyzing outcome=provider_failure code=%s",
            request_id,
            error.code,
        )
        raise HTTPException(status_code=502, detail=detail) from error
    except BaseException:
        if claim is not None:
            viral_analysis_idempotency.complete(
                user_id=user["id"],
                submission_id=submission_id,
                outcome=IdempotencyOutcome(
                    status_code=500,
                    payload={
                        "code": "analysis_internal_error",
                        "stage": "analyzing",
                        "message": "分析服务内部错误。",
                        "retryable": False,
                        "request_id": request_id,
                        "client_submission_id": submission_id or None,
                    },
                ),
            )
        raise
    finally:
        reset_request_id(context_token)


@router.post("/pipeline/upload")
async def run_uploaded_viral_agent_pipeline(
    video_file: UploadFile = File(...),
    source_url: str = Form(default=""),
    industry: str = Form(default="personal_brand"),
    language: str = Form(default="zh"),
    rewrite_length: LengthMode = Form(default="match_source"),
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    request_id = new_request_id()
    context_token = bind_request_id(request_id)
    user = get_authenticated_user(supabase, token)
    try:
        if _viral_upload_lock.locked():
            result = _pipeline_failure(
                request_id=request_id,
                code="asr_busy",
                stage="uploading",
                message="当前已有一个视频正在转写，请稍后重试。",
                retryable=True,
            )
            result.update({"source_type": "uploaded_video_asr", "degraded": False})
            return result
        async with _viral_upload_lock:
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


@router.options("/pipeline/upload", include_in_schema=False)
async def uploaded_viral_pipeline_options() -> Response:
    """Keep non-preflight OPTIONS probes from falling through to FastAPI's 405."""
    return Response(status_code=204)
