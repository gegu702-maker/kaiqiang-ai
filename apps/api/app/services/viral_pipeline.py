from __future__ import annotations

import logging
import shutil
import tempfile
import time
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from postgrest.exceptions import APIError
from supabase import Client

from app.services.asr_service import transcribe_audio
from app.services.llm_provider import LLMProvider
from app.services.video_download_service import DOWNLOAD_FALLBACK, download_video, extract_audio
from app.services.video_link_resolver import extract_best_url, resolve_video_link
from app.services.viral_analyzer import analyze_viral_script

logger = logging.getLogger(__name__)


class ViralPipelineStatus(str, Enum):
    PENDING = "pending"
    RESOLVING_LINK = "resolving_link"
    DOWNLOADING_VIDEO = "downloading_video"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    REWRITING = "rewriting"
    READY = "ready"
    FAILED = "failed"


REWRITE_TITLES = ["版本A", "版本B", "版本C", "老板IP版", "知识分享版", "成交转化版", "故事版", "直播版", "极简口播版"]


def _failed(
    *,
    status: ViralPipelineStatus,
    fallback_reason: str,
    metadata: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_metadata = metadata or {}
    if diagnostics:
        safe_metadata["diagnostics"] = _public_diagnostics(diagnostics)
    return {
        "ok": False,
        "status": ViralPipelineStatus.FAILED,
        "failed_at": status,
        "fallback_reason": fallback_reason,
        "project_id": "",
        "transcript": "",
        "analysis": None,
        "rewrites": [],
        "metadata": safe_metadata,
    }


def _public_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in diagnostics.items() if key != "started_at"}


def _source_summary(source_url: str) -> dict[str, Any]:
    extracted_url = extract_best_url(source_url)
    parsed = urlparse(extracted_url) if extracted_url else None
    return {
        "has_url": bool(extracted_url),
        "domain": parsed.netloc.lower() if parsed else "",
    }


def _safe_error_message(message: str, *, limit: int = 220) -> str:
    return " ".join(str(message or "").split())[:limit]


def _step_start(
    diagnostics: dict[str, Any],
    *,
    step: ViralPipelineStatus,
    user_id: str,
    source: dict[str, Any],
) -> float:
    diagnostics["steps"].append(
        {
            "step": step.value,
            "status": "start",
            "duration_ms": 0,
            "error_code": "",
            "error_type": "",
            "safe_error_message": "",
        }
    )
    logger.info(
        "viral_pipeline_step step=%s status=start user_id=%s source_domain=%s source_has_url=%s",
        step.value,
        user_id,
        source["domain"],
        source["has_url"],
    )
    return time.perf_counter()


def _step_finish(
    diagnostics: dict[str, Any],
    *,
    step: ViralPipelineStatus,
    status: str,
    started_at: float,
    user_id: str,
    source: dict[str, Any],
    error_code: str = "",
    error_type: str = "",
    safe_error_message: str = "",
) -> None:
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    item = {
        "step": step.value,
        "status": status,
        "duration_ms": duration_ms,
        "error_code": error_code,
        "error_type": error_type,
        "safe_error_message": _safe_error_message(safe_error_message),
    }
    diagnostics["duration_ms"] = int((time.perf_counter() - diagnostics["started_at"]) * 1000)
    diagnostics["steps"].append(item)
    if status == "fail":
        diagnostics["failed_at"] = step.value
        diagnostics["error_code"] = error_code
    logger.info(
        "viral_pipeline_step step=%s status=%s duration_ms=%s error_code=%s error_type=%s user_id=%s source_domain=%s source_has_url=%s",
        step.value,
        status,
        duration_ms,
        error_code,
        error_type,
        user_id,
        source["domain"],
        source["has_url"],
    )


def _analysis_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic": analysis.get("topic", ""),
        "hook": analysis.get("hook", ""),
        "selling_points": analysis.get("selling_points", []),
        "structure": analysis.get("structure", []),
        "template": analysis.get("template", ""),
    }


def _fallback_rewrites(analysis: dict[str, Any], transcript: str) -> list[dict[str, str]]:
    topic = str(analysis.get("topic") or "这个爆款视频").strip()
    template = str(analysis.get("template") or "先提出问题，再给出解决方法，最后明确行动。").strip()
    samples = [
        f"今天用一个更清晰的角度，聊聊{topic}。先别急着模仿表面内容，真正值得学习的是它的开头、痛点和行动号召。",
        f"很多人看见爆款只想照着拍，但真正能复用的是结构。围绕{topic}，先抓住用户最在意的问题，再给出解决路径。",
        f"如果你也想做同类内容，先把{topic}拆成三步：开头抓注意力，中间放大问题，结尾给出明确行动。",
        f"我做内容越久越发现，爆款不是靠运气。像{topic}这种内容，背后都有一套可复制的表达节奏。",
        f"一个视频为什么能火？关键不是句子多漂亮，而是它有没有把{topic}讲成一个用户愿意听完的问题。",
        f"如果你正在找更稳定的短视频转化方法，可以先从{topic}这个方向入手，把痛点讲透，把方案讲清楚。",
        f"一开始我也以为爆款靠灵感，后来才明白，像{topic}这样的内容，真正厉害的是先制造问题，再给答案。",
        f"今天直接拆重点：{topic}为什么容易吸引人？因为它先让你意识到问题，再告诉你下一步怎么做。",
        f"{topic}，一句话说清楚：{template}",
    ]
    if transcript and len(samples[-1]) < 30:
        samples[-1] = transcript[:180]
    return [{"title": title, "script": script} for title, script in zip(REWRITE_TITLES, samples, strict=False)]


def _normalize_rewrites(value: Any, analysis: dict[str, Any], transcript: str) -> list[dict[str, str]]:
    fallback = _fallback_rewrites(analysis, transcript)
    if not isinstance(value, list):
        return fallback
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        script = str(item.get("script") or "").strip()
        if title and script:
            normalized.append({"title": title, "script": script})
    existing = {item["title"] for item in normalized}
    normalized.extend(item for item in fallback if item["title"] not in existing)
    return normalized[:9]


async def _generate_nine_rewrites(*, transcript: str, analysis: dict[str, Any], language: str) -> list[dict[str, str]]:
    payload = {
        "language": "中文" if language == "zh" else "English",
        "transcript": transcript,
        "analysis": _analysis_payload(analysis),
        "rewrite_titles": REWRITE_TITLES,
        "requirements": [
            "不要逐字复制原文案",
            "必须是原创表达",
            "适合数字人口播",
            "避免承诺绝对收益",
            "每个版本都要有明确口播节奏",
            "输出严格 JSON，不要 markdown",
        ],
        "schema": {"rewrites": [{"title": "版本标题", "script": "原创口播稿"}]},
    }
    try:
        data = await LLMProvider().generate_json(
            system="你是短视频爆款仿写编导。你只输出合法 JSON，并生成适合数字人口播的原创口播稿。",
            payload=payload,
        )
    except Exception:
        return _fallback_rewrites(analysis, transcript)
    return _normalize_rewrites(data.get("rewrites"), analysis, transcript)


def _update_project_rewrites(supabase: Client, *, project_id: str, rewrites: list[dict[str, str]]) -> None:
    if not project_id:
        return
    try:
        supabase.table("viral_analyses").update({"rewrites": rewrites}).eq("id", project_id).execute()
    except APIError:
        pass


async def run_viral_pipeline(
    supabase: Client,
    *,
    user_id: str,
    email: str,
    source_url: str,
    industry: str,
    language: str,
) -> dict[str, Any]:
    work_dir = Path(tempfile.mkdtemp(prefix="viral-agent-"))
    source = _source_summary(source_url)
    diagnostics: dict[str, Any] = {
        "failed_at": "",
        "error_code": "",
        "duration_ms": 0,
        "source": source,
        "steps": [],
        "started_at": time.perf_counter(),
    }
    try:
        status = ViralPipelineStatus.RESOLVING_LINK
        step_started = _step_start(diagnostics, step=status, user_id=user_id, source=source)
        resolved = await resolve_video_link(source_url)
        metadata = {
            "platform": resolved.get("platform", ""),
            "title": resolved.get("title", ""),
            "description": resolved.get("description", ""),
            "duration": resolved.get("duration", 0),
            "thumbnail": resolved.get("thumbnail", ""),
            "webpage_url": resolved.get("webpage_url", source_url),
            "downloadable": resolved.get("downloadable", False),
        }
        if not resolved.get("ok") or not resolved.get("downloadable"):
            error_code = str(resolved.get("error_code") or resolved.get("errorCode") or "unknown_error")
            _step_finish(
                diagnostics,
                step=status,
                status="fail",
                started_at=step_started,
                user_id=user_id,
                source=source,
                error_code=error_code,
                error_type="resolver_failed",
                safe_error_message=str(resolved.get("fallback_reason") or DOWNLOAD_FALLBACK),
            )
            return _failed(status=status, fallback_reason=resolved.get("fallback_reason") or DOWNLOAD_FALLBACK, metadata=metadata, diagnostics=diagnostics)
        _step_finish(diagnostics, step=status, status="success", started_at=step_started, user_id=user_id, source=source)

        status = ViralPipelineStatus.DOWNLOADING_VIDEO
        step_started = _step_start(diagnostics, step=status, user_id=user_id, source=source)
        downloaded = await download_video(str(resolved.get("webpage_url") or source_url), work_dir)
        metadata.update(
            {
                "title": downloaded.title or metadata["title"],
                "description": downloaded.description or metadata["description"],
                "duration": downloaded.duration or metadata["duration"],
                "thumbnail": downloaded.thumbnail or metadata["thumbnail"],
                "webpage_url": downloaded.webpage_url or metadata["webpage_url"],
                "downloadable": downloaded.ok,
            }
        )
        if not downloaded.ok or not downloaded.video_path:
            _step_finish(
                diagnostics,
                step=status,
                status="fail",
                started_at=step_started,
                user_id=user_id,
                source=source,
                error_code="download_failed",
                error_type="download_failed",
                safe_error_message=downloaded.fallback_reason or DOWNLOAD_FALLBACK,
            )
            return _failed(status=status, fallback_reason=downloaded.fallback_reason or DOWNLOAD_FALLBACK, metadata=metadata, diagnostics=diagnostics)
        _step_finish(diagnostics, step=status, status="success", started_at=step_started, user_id=user_id, source=source)

        status = ViralPipelineStatus.EXTRACTING_AUDIO
        step_started = _step_start(diagnostics, step=status, user_id=user_id, source=source)
        try:
            audio_path = await extract_audio(downloaded.video_path, work_dir)
        except RuntimeError as error:
            _step_finish(
                diagnostics,
                step=status,
                status="fail",
                started_at=step_started,
                user_id=user_id,
                source=source,
                error_code="ffmpeg_failed",
                error_type=error.__class__.__name__,
                safe_error_message=str(error),
            )
            return _failed(status=status, fallback_reason="该视频暂不支持自动解析，请上传视频继续分析。", metadata=metadata, diagnostics=diagnostics)
        _step_finish(diagnostics, step=status, status="success", started_at=step_started, user_id=user_id, source=source)

        status = ViralPipelineStatus.TRANSCRIBING
        step_started = _step_start(diagnostics, step=status, user_id=user_id, source=source)
        asr = await transcribe_audio(audio_path, language)
        if not asr.ok:
            _step_finish(
                diagnostics,
                step=status,
                status="fail",
                started_at=step_started,
                user_id=user_id,
                source=source,
                error_code="asr_failed",
                error_type="asr_failed",
                safe_error_message=asr.fallback_reason or "该视频暂不支持自动转写，请上传视频继续分析。",
            )
            return _failed(status=status, fallback_reason=asr.fallback_reason or "该视频暂不支持自动转写，请上传视频继续分析。", metadata=metadata, diagnostics=diagnostics)
        _step_finish(diagnostics, step=status, status="success", started_at=step_started, user_id=user_id, source=source)

        status = ViralPipelineStatus.ANALYZING
        step_started = _step_start(diagnostics, step=status, user_id=user_id, source=source)
        analysis = await analyze_viral_script(
            supabase,
            user_id=user_id,
            email=email,
            source_url=str(metadata.get("webpage_url") or source_url),
            raw_script=asr.transcript,
            industry=industry,
            language=language,
        )
        _step_finish(diagnostics, step=status, status="success", started_at=step_started, user_id=user_id, source=source)

        status = ViralPipelineStatus.REWRITING
        step_started = _step_start(diagnostics, step=status, user_id=user_id, source=source)
        rewrites = await _generate_nine_rewrites(transcript=asr.transcript, analysis=analysis, language=language)
        project_id = str(analysis.get("project_id") or uuid4())
        _update_project_rewrites(supabase, project_id=project_id, rewrites=rewrites)
        _step_finish(diagnostics, step=status, status="success", started_at=step_started, user_id=user_id, source=source)

        return {
            "ok": True,
            "status": ViralPipelineStatus.READY,
            "failed_at": "",
            "fallback_reason": "",
            "project_id": project_id,
            "transcript": asr.transcript,
            "analysis": _analysis_payload(analysis),
            "rewrites": rewrites,
            "metadata": metadata,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
