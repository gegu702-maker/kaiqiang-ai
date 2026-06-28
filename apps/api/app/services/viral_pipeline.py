from __future__ import annotations

import shutil
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from postgrest.exceptions import APIError
from supabase import Client

from app.services.asr_service import transcribe_audio
from app.services.llm_provider import LLMProvider
from app.services.video_download_service import DOWNLOAD_FALLBACK, download_video, extract_audio
from app.services.video_link_resolver import resolve_video_link
from app.services.viral_analyzer import analyze_viral_script


class ViralPipelineStatus(str, Enum):
    PENDING = "pending"
    RESOLVING_LINK = "resolving_link"
    DOWNLOADING_VIDEO = "downloading_video"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    REWRITING = "rewriting"
    METADATA_FALLBACK = "metadata_fallback"
    READY = "ready"
    FAILED = "failed"


REWRITE_TITLES = ["版本A", "版本B", "版本C", "老板IP版", "知识分享版", "成交转化版", "故事版", "直播版", "极简口播版"]
LANGUAGE_LABELS = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
    "es": "Español",
    "fr": "Français",
    "ru": "Русский",
}


FALLBACK_OPTIONS = ["upload_video", "paste_text"]
METADATA_FALLBACK_WARNING = "已基于链接可读取信息完成初步拆解。由于平台限制，未读取完整视频语音，建议补充原文案可提升准确度。"
INSUFFICIENT_METADATA_MESSAGE = "链接可识别，但可读取内容不足。请粘贴原文案或上传视频以获得完整拆解。"


def _failed(
    *,
    status: ViralPipelineStatus,
    fallback_reason: str,
    metadata: dict[str, Any] | None = None,
    error_code: str = "unknown_error",
) -> dict[str, Any]:
    return {
        "ok": False,
        "success": False,
        "status": ViralPipelineStatus.FAILED,
        "failed_at": status,
        "error_code": error_code,
        "message": fallback_reason,
        "fallback_available": True,
        "fallback_options": FALLBACK_OPTIONS,
        "fallback_reason": fallback_reason,
        "project_id": "",
        "transcript": "",
        "analysis": None,
        "rewrites": [],
        "metadata": metadata or {},
    }


def _analysis_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic": analysis.get("topic", ""),
        "hook": analysis.get("hook", ""),
        "selling_points": analysis.get("selling_points", []),
        "structure": analysis.get("structure", []),
        "template": analysis.get("template", ""),
    }


def _metadata_text(metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    title = str(metadata.get("title") or "").strip()
    description = str(metadata.get("description") or "").strip()
    platform = str(metadata.get("platform") or "").strip()
    duration = metadata.get("duration") or 0
    webpage_url = str(metadata.get("webpage_url") or "").strip()
    if title:
        parts.append(f"标题：{title}")
    if description and description != title:
        parts.append(f"视频描述/分享文案：{description}")
    if platform:
        parts.append(f"平台：{platform}")
    if duration:
        parts.append(f"时长：{duration}秒")
    if webpage_url:
        parts.append(f"链接：{webpage_url}")
    return "\n".join(parts).strip()


def _has_enough_metadata_text(text: str) -> bool:
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    return cjk_count >= 10 or len(text) >= 30


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
    if isinstance(value, str):
        value = [{"title": "基础版", "script": value}]
    if not isinstance(value, list):
        return fallback
    normalized: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            script = item.strip()
            if script:
                normalized.append({"title": f"版本{len(normalized) + 1}", "script": script})
            continue
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or item.get("version") or "").strip()
        script = str(item.get("script") or item.get("content") or item.get("text") or item.get("copy") or "").strip()
        if title and script:
            normalized.append({"title": title, "script": script})
    existing = {item["title"] for item in normalized}
    normalized.extend(item for item in fallback if item["title"] not in existing)
    return normalized[:9]


async def _generate_nine_rewrites(*, transcript: str, analysis: dict[str, Any], language: str) -> list[dict[str, str]]:
    payload = {
        "language": LANGUAGE_LABELS.get(language, "中文"),
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
    return _normalize_rewrites(data.get("rewrites") or data.get("rewrite_versions") or data.get("rewriteVersions") or data.get("scripts"), analysis, transcript)


def _update_project_rewrites(supabase: Client, *, project_id: str, rewrites: list[dict[str, str]]) -> None:
    if not project_id:
        return
    try:
        supabase.table("viral_analyses").update({"rewrites": rewrites}).eq("id", project_id).execute()
    except APIError:
        pass


async def _metadata_fallback_analysis(
    supabase: Client,
    *,
    user_id: str,
    email: str,
    source_url: str,
    metadata: dict[str, Any],
    industry: str,
    language: str,
) -> dict[str, Any]:
    transcript = _metadata_text(metadata)
    if not _has_enough_metadata_text(transcript):
        return _failed(
            status=ViralPipelineStatus.METADATA_FALLBACK,
            fallback_reason=INSUFFICIENT_METADATA_MESSAGE,
            metadata=metadata,
            error_code="insufficient_metadata",
        )

    analysis = await analyze_viral_script(
        supabase,
        user_id=user_id,
        email=email,
        source_url=str(metadata.get("webpage_url") or source_url),
        raw_script=transcript,
        industry=industry,
        language=language,
    )
    rewrites = await _generate_nine_rewrites(transcript=transcript, analysis=analysis, language=language)
    project_id = str(analysis.get("project_id") or uuid4())
    _update_project_rewrites(supabase, project_id=project_id, rewrites=rewrites)
    return {
        "ok": True,
        "success": True,
        "status": ViralPipelineStatus.READY,
        "failed_at": "",
        "error_code": "",
        "message": "",
        "fallback_available": False,
        "fallback_options": [],
        "fallback_reason": "",
        "project_id": project_id,
        "transcript": transcript,
        "analysis": _analysis_payload(analysis),
        "rewrites": rewrites,
        "metadata": metadata,
        "source_type": "link_metadata_fallback",
        "analysis_quality": "partial",
        "warning": METADATA_FALLBACK_WARNING,
    }


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
    try:
        status = ViralPipelineStatus.RESOLVING_LINK
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
            if resolved.get("ok") and (resolved.get("error_code") == "not_downloadable" or not resolved.get("downloadable")):
                metadata["downloadable"] = False
                return await _metadata_fallback_analysis(
                    supabase,
                    user_id=user_id,
                    email=email,
                    source_url=source_url,
                    metadata=metadata,
                    industry=industry,
                    language=language,
                )
            return _failed(
                status=status,
                fallback_reason=resolved.get("message") or resolved.get("fallback_reason") or DOWNLOAD_FALLBACK,
                metadata=metadata,
                error_code=resolved.get("error_code") or "unknown_error",
            )

        status = ViralPipelineStatus.DOWNLOADING_VIDEO
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
            metadata["downloadable"] = False
            return await _metadata_fallback_analysis(
                supabase,
                user_id=user_id,
                email=email,
                source_url=source_url,
                metadata=metadata,
                industry=industry,
                language=language,
            )

        status = ViralPipelineStatus.EXTRACTING_AUDIO
        try:
            audio_path = await extract_audio(downloaded.video_path, work_dir)
        except RuntimeError:
            return _failed(status=status, fallback_reason="该视频暂不支持自动解析，请上传视频继续分析。", metadata=metadata, error_code="not_downloadable")

        status = ViralPipelineStatus.TRANSCRIBING
        asr = await transcribe_audio(audio_path, language)
        if not asr.ok:
            return _failed(
                status=status,
                fallback_reason=asr.fallback_reason or "该视频暂不支持自动转写，请上传视频继续分析。",
                metadata=metadata,
                error_code="not_downloadable",
            )

        status = ViralPipelineStatus.ANALYZING
        analysis = await analyze_viral_script(
            supabase,
            user_id=user_id,
            email=email,
            source_url=str(metadata.get("webpage_url") or source_url),
            raw_script=asr.transcript,
            industry=industry,
            language=language,
        )

        status = ViralPipelineStatus.REWRITING
        rewrites = await _generate_nine_rewrites(transcript=asr.transcript, analysis=analysis, language=language)
        project_id = str(analysis.get("project_id") or uuid4())
        _update_project_rewrites(supabase, project_id=project_id, rewrites=rewrites)

        return {
            "ok": True,
            "success": True,
            "status": ViralPipelineStatus.READY,
            "failed_at": "",
            "error_code": "",
            "message": "",
            "fallback_available": False,
            "fallback_options": [],
            "fallback_reason": "",
            "project_id": project_id,
            "transcript": asr.transcript,
            "analysis": _analysis_payload(analysis),
            "rewrites": rewrites,
            "metadata": metadata,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
