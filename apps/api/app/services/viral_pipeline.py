from __future__ import annotations

import shutil
import tempfile
from enum import Enum
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from postgrest.exceptions import APIError
from supabase import Client

from app.services.asr_service import transcribe_audio
from app.services.llm_provider import LLMProvider
from app.services.video_download_service import DOWNLOAD_FALLBACK, download_video, extract_audio
from app.services.video_link_resolver import resolve_video_link
from app.services.viral_analyzer import FINAL_REWRITE_LIMIT, analyze_viral_script, dedupe_and_diversify_rewrites, is_script_polluted, smooth_spoken_script


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
METADATA_FALLBACK_WARNING = "已基于链接公开信息完成初步拆解。由于平台限制，未读取完整视频语音，补充原文案可提升准确度。"
SHARE_TEXT_FALLBACK_WARNING = "已基于分享文案完成初步拆解。补充原始视频文案可提升准确度。"
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
            "必须像真人直接对观众说话，少用书面总结和方法论标题",
            "多用短句和自然转折，避免连续堆叠“真正、背后、结构、价值、逻辑”等抽象词",
            "不要把每条都写成“先...再...最后...”的教学提纲，除非句子本身像口播",
            "每条建议 100-160 个中文字符，信息要具体但不要编造事实",
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
) -> dict[str, Any]:
    if not _has_enough_metadata_text(share_text):
        return _failed(
            status=ViralPipelineStatus.METADATA_FALLBACK,
            fallback_reason=INSUFFICIENT_METADATA_MESSAGE,
            metadata=metadata or {},
            error_code="insufficient_metadata",
        )

    analysis = await analyze_viral_script(
        supabase,
        user_id=user_id,
        email=email,
        source_url=source_url,
        raw_script=share_text,
        industry=industry,
        language=language,
    )
    rewrites = await _generate_nine_rewrites(transcript=share_text, analysis=analysis, language=language)
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
        "transcript": share_text,
        "analysis": _analysis_payload(analysis),
        "rewrites": rewrites,
        "metadata": metadata or {},
        "source_type": "share_text_fallback",
        "analysis_quality": "partial",
        "warning": SHARE_TEXT_FALLBACK_WARNING,
    }


async def run_viral_pipeline(
    supabase: Client,
    *,
    user_id: str,
    email: str,
    source_url: str,
    industry: str,
    language: str,
    raw_input: str = "",
) -> dict[str, Any]:
    work_dir = Path(tempfile.mkdtemp(prefix="viral-agent-"))
    try:
        share_text = extract_share_text_from_input(raw_input or source_url)
        if _has_enough_metadata_text(share_text):
            return await _share_text_fallback_analysis(
                supabase,
                user_id=user_id,
                email=email,
                source_url=source_url,
                share_text=share_text,
                metadata={
                    "platform": "douyin" if "douyin" in source_url.lower() else "unknown",
                    "title": share_text[:120],
                    "description": share_text,
                    "duration": 0,
                    "thumbnail": "",
                    "webpage_url": source_url,
                    "downloadable": False,
                },
                industry=industry,
                language=language,
            )

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
        metadata_transcript = _metadata_text(metadata)
        if _has_enough_metadata_text(metadata_transcript):
            return await _metadata_fallback_analysis(
                supabase,
                user_id=user_id,
                email=email,
                source_url=source_url,
                metadata=metadata,
                industry=industry,
                language=language,
            )
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

        status = ViralPipelineStatus.TRANSCRIBING
        asr = await transcribe_audio(audio_path, language)
        if not asr.ok:
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
