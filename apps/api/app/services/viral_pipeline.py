from __future__ import annotations

import shutil
import tempfile
import logging
from enum import Enum
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from postgrest.exceptions import APIError
from supabase import Client

from app.services.asr_service import transcribe_audio
from app.services.financial_transcript import CorrectionResult, correct_financial_transcript
from app.services.llm_provider import LLMProvider, LLMProviderError
from app.core.config import settings
from app.services.viral_diagnostics import current_request_id
from app.services.viral_review import create_review_token, verify_review_token
from app.services.video_download_service import DOWNLOAD_FALLBACK, download_video, extract_audio, probe_media_duration
from app.services.video_link_resolver import resolve_video_link
from app.services.viral_analyzer import FINAL_REWRITE_LIMIT, analyze_viral_script, dedupe_and_diversify_rewrites, is_script_polluted, smooth_spoken_script

logger = logging.getLogger(__name__)


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


REWRITE_TITLES = ["版本A：热点反差版", "版本B：用户痛点版", "版本C：商业机会版"]
MIN_REWRITE_CJK_CHARS = 80
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
METADATA_FALLBACK_WARNING = "仅公开信息摘要（非完整拆解）：平台视频未成功下载，ASR=0。完整版已禁用；请上传视频或粘贴原文以获得完整拆解。"
SHARE_TEXT_FALLBACK_WARNING = "仅公开信息摘要（非完整拆解）：未读取视频音轨，ASR=0。完整版已禁用；请上传视频或粘贴原文以获得完整拆解。"
INSUFFICIENT_METADATA_MESSAGE = "链接可识别，但可读取内容不足。请粘贴原文案以获得完整拆解。"
URL_RE = re.compile(r"https?://[^\s\"'<>，。；、]+", re.IGNORECASE)
DOUYIN_COMMAND_RE = re.compile(
    r"(?i)\b[a-z0-9]{2,}:/|复制打开抖音|打开抖音看看|打开看看|长按复制|复制此链接|到抖音|^\s*\d+(?:\.\d+)?\s*"
)


def _failed(
    *,
    status: ViralPipelineStatus,
    fallback_reason: str,
    metadata: dict[str, Any] | None = None,
    error_code: str = "unknown_error",
    retryable: bool = False,
    diagnostic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_id = current_request_id()
    return {
        "ok": False,
        "success": False,
        "status": ViralPipelineStatus.FAILED,
        "failed_at": status,
        "error_code": error_code,
        "code": error_code,
        "stage": status,
        "retryable": retryable,
        "request_id": request_id,
        "message": fallback_reason,
        "fallback_available": True,
        "fallback_options": FALLBACK_OPTIONS,
        "fallback_reason": fallback_reason,
        "project_id": "",
        "transcript": "",
        "analysis": None,
        "rewrites": [],
        "metadata": metadata or {},
        "diagnostic": diagnostic or {},
    }


def _analysis_error_result(
    error: Exception,
    *,
    metadata: dict[str, Any],
    source_type: str,
) -> dict[str, Any]:
    failure_stage = ViralPipelineStatus.ANALYZING
    if isinstance(error, LLMProviderError):
        diagnostic = {
            "http_status": error.http_status,
            "response_length": error.response_length,
            "schema_error": error.schema_error,
        }
        code = error.code
        message = error.message
        retryable = error.retryable
    elif isinstance(error, HTTPException):
        detail = error.detail
        message = str(detail.get("message") if isinstance(detail, dict) else detail)
        code = str(detail.get("code") if isinstance(detail, dict) else "analysis_http_error")
        retryable = bool(detail.get("retryable")) if isinstance(detail, dict) and "retryable" in detail else error.status_code >= 500
        if isinstance(detail, dict) and detail.get("stage") == ViralPipelineStatus.REWRITING.value:
            failure_stage = ViralPipelineStatus.REWRITING
        diagnostic = {"http_status": None, "internal_http_status": error.status_code, "response_length": 0, "schema_error": ""}
        if isinstance(detail, dict):
            diagnostic.update({key: detail[key] for key in ("target_chars", "actual_chars") if key in detail})
    else:
        message = "AI 拆解阶段发生未预期错误。"
        code = "analysis_unexpected_error"
        retryable = True
        diagnostic = {"exception_type": type(error).__name__}
    logger.exception(
        "viral_pipeline request_id=%s stage=%s outcome=failed code=%s retryable=%s diagnostic=%s",
        current_request_id(),
        failure_stage,
        code,
        retryable,
        diagnostic,
    )
    result = _failed(
        status=failure_stage,
        fallback_reason=message,
        metadata=metadata,
        error_code=code,
        retryable=retryable,
        diagnostic=diagnostic,
    )
    result.update({"source_type": source_type, "degraded": source_type.endswith("fallback")})
    return result


def _analysis_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic": analysis.get("topic", ""),
        "hook": analysis.get("hook", ""),
        "selling_points": analysis.get("selling_points", []),
        "structure": analysis.get("structure", []),
        "template": analysis.get("template", ""),
        "core_points": analysis.get("core_points", []),
        "arguments": analysis.get("arguments", []),
        "cases": analysis.get("cases", []),
        "data_points": analysis.get("data_points", []),
    }


def build_metadata_analysis_text(metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    title = str(metadata.get("title") or "").strip()
    description = str(metadata.get("description") or "").strip()
    platform = str(metadata.get("platform") or "").strip()
    duration = metadata.get("duration") or 0
    if title:
        parts.append(f"标题：{title}")
    if description and description != title:
        parts.append(f"视频描述/分享文案：{description}")
    if platform:
        parts.append(f"平台：{platform}")
    if duration:
        parts.append(f"时长：{duration}秒")
    return "\n".join(parts).strip()


def _metadata_text(metadata: dict[str, Any]) -> str:
    return build_metadata_analysis_text(metadata)


def extract_share_text_from_input(raw_input: str) -> str:
    text = URL_RE.sub(" ", raw_input or "")
    text = DOUYIN_COMMAND_RE.sub(" ", text)
    text = text.replace("【", " ").replace("】", "：")
    text = re.sub(r"[\[\]()<>{}]", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*#\s*", " #", text)
    text = re.sub(r"[:：]\s*[:：]+", "：", text)
    return text.strip(" ：，,。;；")


def _has_enough_metadata_text(text: str) -> bool:
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    return cjk_count >= 10 or len(text) >= 30


def _cjk_len(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


PIPELINE_CTA_POOL = [
    "你觉得真正的重点在哪里？评论区说说你的判断。",
    "如果你也在做内容，把这个拆法先记下来，下一次热点就能直接套用。",
    "后面如果产业链继续有新变化，我会再单独拆给你看。",
]


def _pipeline_cta(index: int) -> str:
    return PIPELINE_CTA_POOL[index % len(PIPELINE_CTA_POOL)]


def _with_sentence_end(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    if value[-1] in "。！？!?":
        return value
    return f"{value}。"


def _trim_pipeline_cta(script: str) -> str:
    text = str(script or "")
    for cta in PIPELINE_CTA_POOL:
        text = text.replace(cta, "")
        text = text.replace(cta.rstrip("。！？!"), "")
    return text.strip(" ：:，,。；; ")


def _append_pipeline_cta(script: str, index: int) -> str:
    text = smooth_spoken_script(_trim_pipeline_cta(script))
    return smooth_spoken_script(f"{_with_sentence_end(text)}{_pipeline_cta(index)}")


def _expand_pipeline_rewrite(script: str, *, topic: str, template: str, title: str, index: int = 0) -> str:
    text = smooth_spoken_script(script)
    if _cjk_len(text) >= MIN_REWRITE_CJK_CHARS and not is_script_polluted(text):
        return text
    topic_text = topic or "这个热点"
    styles = [
        (
            f"你有没有发现，{topic_text}让人停下来的地方，往往不是事件本身。"
            "而是大家第一眼以为很简单，往下看才发现里面有一个反差。"
            "先把这个反差讲出来，再补一个你的判断，观众会更愿意听下去。"
        ),
        (
            f"如果你经常追热点，却不知道怎么把{topic_text}拍成自己的内容，可以先换到用户视角。"
            "别急着讲结论，先说大家最容易卡住的问题，再给一个能马上开拍的角度。"
        ),
        (
            f"{topic_text}不只是一个新闻点，也可能是一个机会信号。"
            "你可以看谁的需求变了，谁的供给还没跟上，再判断这个话题能不能延伸成自己的选题。"
        ),
        (
            f"站在老板视角看，{topic_text}不是单纯热点，而是一次判断趋势的练习。"
            "别急着看热闹，先看谁的位置变了，谁的机会变多了，谁需要重新调整打法。"
        ),
        (
            f"把{topic_text}讲成知识口播，可以先讲背景，再讲反差，最后讲它对普通人的启发。"
            "这样观众听到的不只是消息，而是一套以后还能复用的判断方法。"
        ),
        (
            f"这条内容可以讲成一个转折故事：大家一开始只看到{topic_text}的表面，"
            "但越拆越会发现，真正推动讨论的是藏在细节里的变化。"
        ),
        (
            f"家人们先别划走，{topic_text}这件事表面像新闻，其实很适合拆成一个互动话题。"
            "我们先看矛盾点，再看谁会受到影响，最后看你能不能把它改成自己的选题。"
        ),
        (
            f"一句话拆{topic_text}：别只看结论，要看它为什么在这个时间点被讨论。"
            "开头用反差抓人，中间补关键线索，结尾给观众一个参与判断的理由。"
        ),
        (
            f"如果你想把{topic_text}改成能带来咨询的口播，别急着堆信息。"
            "先指出观众正在错过什么，再给一个清晰判断，最后把下一步行动说具体。"
        ),
    ]
    opening = text or styles[index % len(styles)]
    return _append_pipeline_cta(opening, index)


def _fallback_rewrites(analysis: dict[str, Any], transcript: str) -> list[dict[str, str]]:
    topic = str(analysis.get("topic") or "这个爆款视频").strip()
    template = str(analysis.get("template") or "先提出问题，再给出解决方法，最后明确行动。").strip()
    samples = [
        f"今天换个更好懂的角度，聊聊{topic}。别先忙着照搬原视频，先看它为什么能让人停下来：表面是热点，里面其实藏着一个和观众有关的问题。",
        f"很多人看见爆款就想照着拍，但用户听到一半就划走，通常是因为你只复述了信息。围绕{topic}，先说清楚他们关心什么，再给一个能立刻用上的表达角度。",
        f"如果你也想做同类内容，可以把{topic}拆成三句话：第一句抓注意力，第二句讲清楚为什么和观众有关，第三句给出你的判断和下一步动作。",
        f"我做内容越久越发现，爆款不是靠运气。像{topic}这种内容，背后都有一套可复制的表达节奏。",
        f"一个视频为什么能火？关键不是句子多漂亮，而是它有没有把{topic}讲成一个用户愿意听完的问题。",
        f"如果你正在找更稳定的短视频转化方法，可以先从{topic}这个方向入手，把痛点讲透，把方案讲清楚。",
        f"一开始我也以为爆款靠灵感，后来才明白，像{topic}这样的内容，真正厉害的是先制造问题，再给答案。",
        f"今天直接拆重点：{topic}为什么容易吸引人？因为它先让你意识到问题，再告诉你下一步怎么做。",
        f"如果只用一句话拆{topic}，我会提醒你别只看标题。真正重要的是它背后的反差、线索和后续变化，这些才是观众愿意听完并继续互动的原因。",
    ]
    if transcript and len(samples[-1]) < 30:
        samples[-1] = transcript[:180]
    rewrites = [
        {"title": title, "script": _expand_pipeline_rewrite(script, topic=topic, template=template, title=title, index=index)}
        for index, (title, script) in enumerate(zip(REWRITE_TITLES, samples, strict=False))
    ]
    return dedupe_and_diversify_rewrites(
        rewrites,
        topic=topic,
        hook=str(analysis.get("hook") or "先用一个反差问题抓住注意力。"),
        template=template,
        language="zh",
        limit=FINAL_REWRITE_LIMIT,
    )


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
                title = f"版本{len(normalized) + 1}"
                normalized.append({"title": title, "script": _expand_pipeline_rewrite(script, topic=str(analysis.get("topic") or "这个爆款视频"), template=str(analysis.get("template") or ""), title=title, index=len(normalized))})
            continue
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or item.get("version") or "").strip()
        script = str(item.get("script") or item.get("content") or item.get("text") or item.get("copy") or "").strip()
        if title and script:
            normalized.append({"title": title, "script": _expand_pipeline_rewrite(script, topic=str(analysis.get("topic") or "这个爆款视频"), template=str(analysis.get("template") or ""), title=title, index=len(normalized))})
    existing = {item["title"] for item in normalized}
    normalized.extend(item for item in fallback if item["title"] not in existing)
    return dedupe_and_diversify_rewrites(
        normalized,
        topic=str(analysis.get("topic") or "这个爆款视频"),
        hook=str(analysis.get("hook") or "先用一个反差问题抓住注意力。"),
        template=str(analysis.get("template") or ""),
        language="zh",
        limit=FINAL_REWRITE_LIMIT,
    )


async def _generate_nine_rewrites(*, transcript: str, analysis: dict[str, Any], language: str, rewrite_length: str = "short") -> list[dict[str, str]]:
    length_guidance = {
        "short": "30–60 秒，中文约 120–240 字",
        "medium": "60–120 秒，中文约 240–500 字",
        "full": "完整版，保留原内容主要观点、论据、案例和数据；长视频中文通常 500–1200 字",
    }.get(rewrite_length, "30–60 秒，中文约 120–240 字")
    payload = {
        "language": LANGUAGE_LABELS.get(language, "中文"),
        "transcript": transcript,
        "analysis": _analysis_payload(analysis),
        "rewrite_titles": REWRITE_TITLES,
        "requirements": [
            "不要逐字复制原文案",
            "必须是原创表达",
            "适合数字人口播",
            "必须像真人直接对观众说话，少用书面总结和方法论标题",
            "多用短句和自然转折，避免连续堆叠“真正、背后、结构、价值、逻辑”等抽象词",
            "不要把每条都写成“先...再...最后...”的教学提纲，除非句子本身像口播",
            "信息要具体但不要编造事实",
            f"本次长度必须符合：{length_guidance}",
            "避免承诺绝对收益",
            "每个版本都要有明确口播节奏",
            "只生成 3 条高质量版本：版本A热点反差版、版本B用户痛点版、版本C商业机会版",
            "每个版本必须使用不同骨架：热点反差、用户痛点、商业机会",
            "每条文案开头和结尾不能重复，CTA 不能完全相同",
            "同一批文案中“下一条继续拆”最多出现 1 次，“先收藏”最多出现 1 次，不要每条都以“关注我”结尾",
            "不要重复“普通人看结果，懂内容的人会先问”这类固定句式",
            "不要重复使用“这类内容好用的地方”“既能承接热点流量，也能展示你的专业判断”“想看我继续拆这个方向”“评论区留一个继续”等句式骨架",
            "script 只能写最终口播成稿，禁止出现模板说明、结构说明、可复用模板、括号结构或版本解释",
            "不要写“可复用模板是”“这个版本适合”“建议用户”“（疑问/反常识开头）+”等生成策略说明",
            "输出严格 JSON，不要 markdown",
        ],
        "schema": {"rewrites": [{"title": "版本标题", "script": "原创口播稿"}]},
    }
    try:
        data = await LLMProvider().generate_json(
            system="你是短视频爆款仿写编导。你只输出合法 JSON，并生成适合数字人口播的原创口播稿。",
            payload=payload,
            max_tokens=8000 if rewrite_length == "full" else 5000,
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


def _format_timestamp(seconds: float) -> str:
    minutes, remainder = divmod(max(seconds, 0.0), 60)
    return f"{int(minutes):02d}:{int(remainder):02d}"


def _log_diagnostics(diagnostics: dict[str, Any]) -> None:
    logger.info(
        "viral_analysis_diagnostics source_type=%s video_duration_seconds=%s asr_coverage_seconds=%s "
        "transcript_chars=%s segment_count=%s fallback=%s prompt_input_chars=%s output_chars=%s",
        diagnostics.get("source_type"),
        diagnostics.get("video_duration_seconds"),
        diagnostics.get("asr_coverage_seconds"),
        diagnostics.get("transcript_chars"),
        diagnostics.get("segment_count"),
        diagnostics.get("fallback"),
        diagnostics.get("prompt_input_chars"),
        diagnostics.get("output_chars"),
    )


async def _process_video_path(
    supabase: Client,
    *,
    video_path: Path,
    work_dir: Path,
    user_id: str,
    email: str,
    source_url: str,
    industry: str,
    language: str,
    rewrite_length: str,
    source_type: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    request_id = current_request_id()
    logger.info(
        "viral_pipeline request_id=%s stage=media_probe outcome=started source_type=%s video_bytes=%s",
        request_id,
        source_type,
        video_path.stat().st_size if video_path.exists() else -1,
    )
    duration = float(metadata.get("duration") or 0.0)
    if not duration:
        try:
            duration = await probe_media_duration(video_path)
        except RuntimeError as error:
            result = _failed(
                status=ViralPipelineStatus.EXTRACTING_AUDIO,
                fallback_reason=str(error),
                metadata=metadata,
                error_code="media_probe_failed",
            )
            result.update({"source_type": source_type, "degraded": False})
            return result
        metadata["duration"] = duration
    logger.info(
        "viral_pipeline request_id=%s stage=media_probe outcome=completed duration_seconds=%.3f",
        request_id,
        duration,
    )
    if duration > settings.viral_max_video_duration_seconds:
        return _failed(
            status=ViralPipelineStatus.EXTRACTING_AUDIO,
            fallback_reason=f"视频时长 {duration:.1f} 秒，超过 {settings.viral_max_video_duration_seconds} 秒限制。",
            metadata=metadata,
            error_code="video_too_long",
            retryable=False,
            diagnostic={
                "actual_duration_seconds": round(duration, 3),
                "allowed_duration_seconds": settings.viral_max_video_duration_seconds,
            },
        )

    logger.info("viral_pipeline request_id=%s stage=extracting_audio outcome=started", request_id)
    try:
        audio_path = await extract_audio(video_path, work_dir)
    except RuntimeError as error:
        result = _failed(
            status=ViralPipelineStatus.EXTRACTING_AUDIO,
            fallback_reason=str(error),
            metadata=metadata,
            error_code="audio_extraction_failed",
        )
        result["source_type"] = source_type
        result["degraded"] = False
        return result
    logger.info(
        "viral_pipeline request_id=%s stage=extracting_audio outcome=completed audio_bytes=%s",
        request_id,
        audio_path.stat().st_size if audio_path.exists() else -1,
    )

    asr = await transcribe_audio(audio_path, language)
    if not asr.ok:
        logger.warning(
            "viral_pipeline request_id=%s stage=transcribing outcome=failed code=%s retryable=%s diagnostic=%r",
            request_id,
            asr.error_code or "asr_failed",
            asr.retryable,
            asr.diagnostic,
        )
        result = _failed(
            status=ViralPipelineStatus.TRANSCRIBING,
            fallback_reason=asr.fallback_reason,
            metadata=metadata,
            error_code=asr.error_code or "asr_failed",
            retryable=asr.retryable,
            diagnostic={"provider": asr.provider, "error": asr.diagnostic},
        )
        result.update({"source_type": source_type, "degraded": False, "asr_provider": asr.provider})
        return result

    raw_segments = asr.segments or []
    raw_timeline = [
        {"segment_index": index, "start": segment.start, "end": segment.end, "timestamp": f"{_format_timestamp(segment.start)}–{_format_timestamp(segment.end)}", "text": segment.text}
        for index, segment in enumerate(raw_segments)
    ]
    if settings.viral_asr_domain.strip().lower() == "financial":
        correction = await correct_financial_transcript(raw_segments, language)
    else:
        correction = CorrectionResult(
            corrected_transcript=asr.transcript,
            corrected_segments=raw_segments,
            corrections=[],
            review_segments=[],
            quality_passed=True,
            provider="none",
        )
    corrected_transcript = correction.corrected_transcript
    timeline = [
        {"segment_index": index, "start": segment.start, "end": segment.end, "timestamp": f"{_format_timestamp(segment.start)}–{_format_timestamp(segment.end)}", "text": segment.text}
        for index, segment in enumerate(correction.corrected_segments)
    ]
    correction_count = sum(int(item.get("count") or 1) for item in correction.corrections)
    coverage_ratio = asr.coverage_seconds / duration if duration else 1.0
    degraded = bool(duration and coverage_ratio < 0.8)
    warnings = ["自动转写已进行AI金融术语校正，仍建议结合原视频人工复核。"] if correction.provider != "none" else []
    if degraded:
        warnings.append(f"ASR 仅覆盖到 {asr.coverage_seconds:.1f}/{duration:.1f} 秒，结果可能不完整。")
    warning = " ".join(warnings)
    correction_diagnostics = {
        "source_type": source_type,
        "video_duration_seconds": round(duration, 3),
        "asr_coverage_seconds": round(asr.coverage_seconds, 3),
        "transcript_chars": len(corrected_transcript),
        "raw_transcript_chars": len(asr.transcript),
        "corrected_transcript_chars": len(corrected_transcript),
        "segment_count": len(timeline),
        "correction_count": correction_count,
        "review_segment_count": len(correction.review_segments),
        "fallback": False,
        "prompt_input_chars": 0,
        "output_chars": 0,
    }
    if not correction.quality_passed:
        review_context = {
            "request_id": request_id,
            "raw_transcript": asr.transcript,
            "raw_timeline": raw_timeline,
            "suggested_timeline": timeline,
            "review_indices": sorted({int(item["segment_index"]) for item in correction.review_segments if int(item.get("segment_index", -1)) >= 0}),
            "global_review_reasons": [
                str(item.get("reason") or "校正服务异常")
                for item in correction.review_segments
                if int(item.get("segment_index", -1)) < 0
            ],
            "metadata": metadata,
            "diagnostics": correction_diagnostics,
            "source_type": source_type,
            "corrections": correction.corrections,
        }
        result = _failed(
            status=ViralPipelineStatus.TRANSCRIBING,
            fallback_reason="金融语义质量检查发现仍需人工确认的片段，已停止下游拆解，避免错误扩散。",
            metadata=metadata,
            error_code="transcript_review_required",
            retryable=False,
            diagnostic={"review_segment_count": len(correction.review_segments)},
        )
        result.update(
            {
                "source_type": source_type,
                "degraded": True,
                "transcript": corrected_transcript,
                "raw_transcript": asr.transcript,
                "timeline": timeline,
                "raw_timeline": raw_timeline,
                "corrections": correction.corrections,
                "correction_count": correction_count,
                "review_segments": correction.review_segments,
                "review_context": review_context,
                "review_token": create_review_token(review_context),
                "diagnostics": correction_diagnostics,
                "warning": warning,
            }
        )
        _log_diagnostics(correction_diagnostics)
        return result
    logger.info(
        "viral_pipeline request_id=%s stage=analyzing outcome=started transcript_chars=%s segment_count=%s coverage_seconds=%.3f",
        request_id,
        len(corrected_transcript),
        len(timeline),
        asr.coverage_seconds,
    )
    try:
        analysis = await analyze_viral_script(
            supabase,
            user_id=user_id,
            email=email,
            source_url=source_url,
            raw_script=corrected_transcript,
            industry=industry,
            language=language,
            rewrite_length=rewrite_length,
        )
    except Exception as error:
        return _analysis_error_result(error, metadata=metadata, source_type=source_type)
    rewrites = analysis.get("rewrites") or await _generate_nine_rewrites(
        transcript=corrected_transcript,
        analysis=analysis,
        language=language,
        rewrite_length=rewrite_length,
    )
    project_id = str(analysis.get("project_id") or uuid4())
    diagnostics = {
        "source_type": source_type,
        "video_duration_seconds": round(duration, 3),
        "asr_coverage_seconds": round(asr.coverage_seconds, 3),
        "transcript_chars": len(corrected_transcript),
        "raw_transcript_chars": len(asr.transcript),
        "corrected_transcript_chars": len(corrected_transcript),
        "segment_count": len(timeline),
        "correction_count": correction_count,
        "review_segment_count": len(correction.review_segments),
        "fallback": False,
        "prompt_input_chars": analysis.get("diagnostics", {}).get("prompt_input_chars", 0),
        "output_chars": sum(len(item.get("script", "")) for item in rewrites),
    }
    _log_diagnostics(diagnostics)
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
        "transcript": corrected_transcript,
        "raw_transcript": asr.transcript,
        "timeline": timeline,
        "raw_timeline": raw_timeline,
        "corrections": correction.corrections,
        "correction_count": correction_count,
        "review_segments": correction.review_segments,
        "analysis": _analysis_payload(analysis),
        "rewrites": rewrites,
        "metadata": metadata,
        "source_type": source_type,
        "analysis_quality": "partial" if degraded else "full",
        "degraded": degraded,
        "warning": warning,
        "asr_provider": asr.provider,
        "diagnostics": diagnostics,
        "code": "",
        "stage": ViralPipelineStatus.READY,
        "retryable": False,
        "request_id": request_id,
    }


async def _metadata_fallback_analysis(
    supabase: Client,
    *,
    user_id: str,
    email: str,
    source_url: str,
    metadata: dict[str, Any],
    industry: str,
    language: str,
    rewrite_length: str = "short",
) -> dict[str, Any]:
    transcript = _metadata_text(metadata)
    if not _has_enough_metadata_text(transcript):
        return _failed(
            status=ViralPipelineStatus.METADATA_FALLBACK,
            fallback_reason=INSUFFICIENT_METADATA_MESSAGE,
            metadata=metadata,
            error_code="insufficient_metadata",
        )

    logger.info(
        "viral_pipeline request_id=%s stage=analyzing outcome=started source_type=link_metadata_fallback transcript_chars=%s",
        current_request_id(),
        len(transcript),
    )
    try:
        analysis = await analyze_viral_script(
            supabase,
            user_id=user_id,
            email=email,
            source_url=str(metadata.get("webpage_url") or source_url),
            raw_script=transcript,
            industry=industry,
            language=language,
            rewrite_length=rewrite_length,
            source_scope="public_metadata",
        )
    except Exception as error:
        return _analysis_error_result(error, metadata=metadata, source_type="link_metadata_fallback")
    rewrites = analysis.get("rewrites") or await _generate_nine_rewrites(transcript=transcript, analysis=analysis, language=language, rewrite_length="short")
    project_id = str(analysis.get("project_id") or uuid4())
    _update_project_rewrites(supabase, project_id=project_id, rewrites=rewrites)
    diagnostics = {
        "source_type": "link_metadata_fallback",
        "video_duration_seconds": float(metadata.get("duration") or 0),
        "asr_coverage_seconds": 0.0,
        "transcript_chars": len(transcript),
        "segment_count": 0,
        "fallback": True,
        "prompt_input_chars": analysis.get("diagnostics", {}).get("prompt_input_chars", 0),
        "output_chars": sum(len(item.get("script", "")) for item in rewrites),
    }
    _log_diagnostics(diagnostics)
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
        "degraded": True,
        "warning": METADATA_FALLBACK_WARNING,
        "summary_label": "仅公开信息摘要",
        "full_rewrite_available": False,
        "rewrite_length_requested": rewrite_length,
        "rewrite_length_effective": "short",
        "diagnostics": diagnostics,
    }


async def _share_text_fallback_analysis(
    supabase: Client,
    *,
    user_id: str,
    email: str,
    source_url: str,
    share_text: str,
    metadata: dict[str, Any] | None,
    industry: str,
    language: str,
    rewrite_length: str = "short",
) -> dict[str, Any]:
    if not _has_enough_metadata_text(share_text):
        return _failed(
            status=ViralPipelineStatus.METADATA_FALLBACK,
            fallback_reason=INSUFFICIENT_METADATA_MESSAGE,
            metadata=metadata or {},
            error_code="insufficient_metadata",
        )

    logger.info(
        "viral_pipeline request_id=%s stage=analyzing outcome=started source_type=share_text_fallback transcript_chars=%s",
        current_request_id(),
        len(share_text),
    )
    try:
        analysis = await analyze_viral_script(
            supabase,
            user_id=user_id,
            email=email,
            source_url=source_url,
            raw_script=share_text,
            industry=industry,
            language=language,
            rewrite_length="short",
            source_scope="public_metadata",
        )
    except Exception as error:
        return _analysis_error_result(error, metadata=metadata or {}, source_type="share_text_fallback")
    rewrites = analysis.get("rewrites") or await _generate_nine_rewrites(transcript=share_text, analysis=analysis, language=language, rewrite_length="short")
    project_id = str(analysis.get("project_id") or uuid4())
    _update_project_rewrites(supabase, project_id=project_id, rewrites=rewrites)
    diagnostics = {
        "source_type": "share_text_fallback",
        "video_duration_seconds": float((metadata or {}).get("duration") or 0),
        "asr_coverage_seconds": 0.0,
        "transcript_chars": len(share_text),
        "segment_count": 0,
        "fallback": True,
        "prompt_input_chars": analysis.get("diagnostics", {}).get("prompt_input_chars", 0),
        "output_chars": sum(len(item.get("script", "")) for item in rewrites),
    }
    _log_diagnostics(diagnostics)
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
        "transcript": share_text,
        "analysis": _analysis_payload(analysis),
        "rewrites": rewrites,
        "metadata": metadata or {},
        "source_type": "share_text_fallback",
        "analysis_quality": "partial",
        "degraded": True,
        "warning": SHARE_TEXT_FALLBACK_WARNING,
        "summary_label": "仅公开信息摘要",
        "full_rewrite_available": False,
        "rewrite_length_requested": rewrite_length,
        "rewrite_length_effective": "short",
        "diagnostics": diagnostics,
        "code": "",
        "stage": ViralPipelineStatus.READY,
        "retryable": False,
        "request_id": current_request_id(),
    }


async def continue_reviewed_viral_pipeline(
    supabase: Client,
    *,
    user_id: str,
    email: str,
    review_context: dict[str, Any],
    review_token: str,
    confirmed_segments: list[dict[str, Any]],
    source_url: str,
    industry: str,
    language: str,
    rewrite_length: str,
) -> dict[str, Any]:
    if not verify_review_token(review_context, review_token):
        return _failed(
            status=ViralPipelineStatus.TRANSCRIBING,
            fallback_reason="复核会话已失效，请重新上传视频。",
            error_code="review_token_invalid",
            retryable=False,
        )

    raw_timeline = review_context.get("raw_timeline") or []
    suggested_timeline = review_context.get("suggested_timeline") or []
    review_indices = {int(index) for index in (review_context.get("review_indices") or [])}
    global_review_reasons = review_context.get("global_review_reasons") or []
    if global_review_reasons:
        return _failed(
            status=ViralPipelineStatus.TRANSCRIBING,
            fallback_reason="自动校正服务未完成，无法通过局部分段确认继续拆解，请重新上传视频。",
            error_code="review_context_invalid",
            retryable=True,
            diagnostic={"global_review_reason_count": len(global_review_reasons)},
        )
    if not raw_timeline or len(raw_timeline) != len(suggested_timeline):
        return _failed(
            status=ViralPipelineStatus.TRANSCRIBING,
            fallback_reason="复核分段数据不完整，请重新上传视频。",
            error_code="review_context_invalid",
            retryable=False,
        )

    submitted = {int(item.get("segment_index", -1)): item for item in confirmed_segments if isinstance(item, dict)}
    missing = sorted(index for index in review_indices if not submitted.get(index, {}).get("confirmed"))
    if missing:
        return _failed(
            status=ViralPipelineStatus.TRANSCRIBING,
            fallback_reason=f"仍有 {len(missing)} 个待复核分段未确认。",
            error_code="review_segments_unconfirmed",
            retryable=False,
            diagnostic={"unconfirmed_indices": missing},
        )

    timeline: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for index, suggested in enumerate(suggested_timeline):
        raw = raw_timeline[index]
        item = submitted.get(index)
        text = str(item.get("corrected_text") if item else suggested.get("text") or "").strip()
        if not text or "�" in text:
            return _failed(
                status=ViralPipelineStatus.TRANSCRIBING,
                fallback_reason=f"第 {index + 1} 段仍为空或包含U+FFFD乱码。",
                error_code="review_text_invalid",
                retryable=False,
                diagnostic={"segment_index": index},
            )
        timeline.append({**suggested, "text": text})
        if index in review_indices or text != str(raw.get("text") or ""):
            audit.append(
                {
                    "segment_index": index,
                    "start": float(raw.get("start") or 0),
                    "end": float(raw.get("end") or 0),
                    "original_text": str(raw.get("text") or ""),
                    "corrected_text": text,
                    "source": "human_confirmed" if index in review_indices else "ai_constrained",
                    "confirmed": index not in review_indices or bool(item and item.get("confirmed")),
                }
            )

    corrected_transcript = "\n".join(str(item["text"]) for item in timeline).strip()
    if "�" in corrected_transcript:
        return _failed(
            status=ViralPipelineStatus.TRANSCRIBING,
            fallback_reason="确认稿仍包含U+FFFD乱码。",
            error_code="review_text_invalid",
            retryable=False,
        )

    try:
        analysis = await analyze_viral_script(
            supabase,
            user_id=user_id,
            email=email,
            source_url=source_url,
            raw_script=corrected_transcript,
            industry=industry,
            language=language,
            rewrite_length=rewrite_length,
        )
    except Exception as error:
        return _analysis_error_result(
            error,
            metadata=review_context.get("metadata") or {},
            source_type=str(review_context.get("source_type") or "uploaded_video_asr"),
        )
    rewrites = analysis.get("rewrites") or await _generate_nine_rewrites(
        transcript=corrected_transcript,
        analysis=analysis,
        language=language,
        rewrite_length=rewrite_length,
    )
    project_id = str(analysis.get("project_id") or uuid4())
    diagnostics = dict(review_context.get("diagnostics") or {})
    diagnostics.update(
        {
            "transcript_chars": len(corrected_transcript),
            "corrected_transcript_chars": len(corrected_transcript),
            "review_segment_count": len(review_indices),
            "confirmed_review_segment_count": len(review_indices),
            "output_chars": sum(len(item.get("script", "")) for item in rewrites),
        }
    )
    _log_diagnostics(diagnostics)
    return {
        "ok": True,
        "success": True,
        "status": ViralPipelineStatus.READY,
        "failed_at": "",
        "error_code": "",
        "code": "",
        "stage": ViralPipelineStatus.READY,
        "retryable": False,
        "request_id": current_request_id(),
        "original_request_id": review_context.get("request_id", ""),
        "message": "",
        "fallback_available": False,
        "fallback_options": [],
        "fallback_reason": "",
        "project_id": project_id,
        "transcript": corrected_transcript,
        "raw_transcript": str(review_context.get("raw_transcript") or ""),
        "timeline": timeline,
        "raw_timeline": raw_timeline,
        "corrections": review_context.get("corrections") or [],
        "correction_audit": audit,
        "correction_count": len(audit),
        "review_segments": [],
        "analysis": _analysis_payload(analysis),
        "rewrites": rewrites,
        "metadata": review_context.get("metadata") or {},
        "source_type": review_context.get("source_type") or "uploaded_video_asr",
        "analysis_quality": "human_reviewed",
        "degraded": False,
        "warning": "自动转写已完成AI校正和逐段人工确认。",
        "asr_provider": "faster-whisper",
        "diagnostics": diagnostics,
    }


async def run_uploaded_viral_pipeline(
    supabase: Client,
    *,
    upload: UploadFile,
    user_id: str,
    email: str,
    source_url: str,
    industry: str,
    language: str,
    rewrite_length: str,
) -> dict[str, Any]:
    """Analyze an uploaded file directly. The file is never persisted to Storage."""
    work_dir = Path(tempfile.mkdtemp(prefix="viral-upload-"))
    suffix = Path(upload.filename or "upload.mp4").suffix.lower()
    if suffix not in {".mp4", ".mov", ".mkv", ".webm", ".m4v"}:
        shutil.rmtree(work_dir, ignore_errors=True)
        return _failed(status=ViralPipelineStatus.PENDING, fallback_reason="不支持的视频格式。", error_code="unsupported_video_format")
    video_path = work_dir / f"source{suffix}"
    max_bytes = settings.viral_max_download_mb * 1024 * 1024
    total = 0
    try:
        try:
            with video_path.open("wb") as target:
                while chunk := await upload.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        return _failed(
                            status=ViralPipelineStatus.PENDING,
                            fallback_reason=f"视频超过 {settings.viral_max_download_mb}MB 限制。",
                            error_code="video_too_large",
                        )
                    target.write(chunk)
        except (OSError, RuntimeError) as error:
            return _failed(
                status=ViralPipelineStatus.PENDING,
                fallback_reason=f"上传流读取中断：{error}",
                error_code="upload_interrupted",
                retryable=True,
            )
        logger.info(
            "viral_pipeline request_id=%s stage=upload_received outcome=completed filename_suffix=%s uploaded_bytes=%s expected_bytes=%s",
            current_request_id(),
            suffix,
            total,
            getattr(upload, "size", None) if getattr(upload, "size", None) is not None else -1,
        )
        metadata = {
            "platform": "upload",
            "title": Path(upload.filename or "上传视频").stem,
            "description": "",
            "duration": 0,
            "thumbnail": "",
            "webpage_url": source_url,
            "downloadable": True,
        }
        return await _process_video_path(
            supabase,
            video_path=video_path,
            work_dir=work_dir,
            user_id=user_id,
            email=email,
            source_url=source_url,
            industry=industry,
            language=language,
            rewrite_length=rewrite_length,
            source_type="uploaded_video_asr",
            metadata=metadata,
        )
    finally:
        await upload.close()
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.info(
            "viral_pipeline request_id=%s stage=cleanup outcome=completed temp_exists=%s",
            current_request_id(),
            work_dir.exists(),
        )


async def run_viral_pipeline(
    supabase: Client,
    *,
    user_id: str,
    email: str,
    source_url: str,
    industry: str,
    language: str,
    raw_input: str = "",
    rewrite_length: str = "short",
) -> dict[str, Any]:
    work_dir = Path(tempfile.mkdtemp(prefix="viral-agent-"))
    try:
        logger.info("viral_pipeline request_id=%s stage=resolving_link outcome=started", current_request_id())
        share_text = extract_share_text_from_input(raw_input or source_url)
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
        logger.info(
            "viral_pipeline request_id=%s stage=resolving_link outcome=completed ok=%s platform=%s duration_seconds=%s downloadable=%s title_chars=%s description_chars=%s error_code=%s",
            current_request_id(),
            bool(resolved.get("ok")),
            metadata["platform"],
            metadata["duration"],
            metadata["downloadable"],
            len(str(metadata["title"] or "")),
            len(str(metadata["description"] or "")),
            resolved.get("error_code") or "",
        )
        if not resolved.get("ok") or not resolved.get("downloadable"):
            if _has_enough_metadata_text(share_text):
                return await _share_text_fallback_analysis(
                    supabase,
                    user_id=user_id,
                    email=email,
                    source_url=source_url,
                    share_text=share_text,
                    metadata=metadata,
                    industry=industry,
                    language=language,
                    rewrite_length=rewrite_length,
                )
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
                    rewrite_length=rewrite_length,
                )
            return _failed(
                status=status,
                fallback_reason=resolved.get("message") or resolved.get("fallback_reason") or DOWNLOAD_FALLBACK,
                metadata=metadata,
                error_code=resolved.get("error_code") or "unknown_error",
            )

        status = ViralPipelineStatus.DOWNLOADING_VIDEO
        logger.info("viral_pipeline request_id=%s stage=downloading_video outcome=started", current_request_id())
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
            logger.warning(
                "viral_pipeline request_id=%s stage=downloading_video outcome=fallback reason_code=%s",
                current_request_id(),
                getattr(downloaded, "error_code", "") or "not_downloadable",
            )
            metadata["downloadable"] = False
            return await _metadata_fallback_analysis(
                supabase,
                user_id=user_id,
                email=email,
                source_url=source_url,
                metadata=metadata,
                industry=industry,
                language=language,
                rewrite_length=rewrite_length,
            )

        return await _process_video_path(
            supabase,
            video_path=downloaded.video_path,
            work_dir=work_dir,
            user_id=user_id,
            email=email,
            source_url=str(metadata.get("webpage_url") or source_url),
            industry=industry,
            language=language,
            rewrite_length=rewrite_length,
            source_type="link_video_asr",
            metadata=metadata,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.info(
            "viral_pipeline request_id=%s stage=cleanup outcome=completed temp_exists=%s",
            current_request_id(),
            work_dir.exists(),
        )
