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
from app.services.viral_analyzer import analyze_viral_script, dedupe_and_diversify_rewrites, is_script_polluted, sanitize_rewrite_script


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
    "想看我继续拆这个方向，评论区留一个“继续”。",
    "你觉得这背后是机会还是风险？评论区聊聊。",
    "先别急着跟风，收藏起来，下次判断热点时再看。",
    "关注我，下一条拆它背后的商业逻辑。",
    "你还想拆哪个热门视频？把链接发我。",
    "如果你也在做内容，这个角度可以直接拿去改。",
    "看到这里，你已经比大多数人多想了一层。",
    "这类热点别只看热闹，关键是看它背后的机会。",
    "把你的行业发在评论区，我帮你换成能拍的选题。",
]


def _pipeline_cta(index: int) -> str:
    return PIPELINE_CTA_POOL[index % len(PIPELINE_CTA_POOL)]


def _expand_pipeline_rewrite(script: str, *, topic: str, template: str, title: str, index: int = 0) -> str:
    text = sanitize_rewrite_script(script)
    if _cjk_len(text) >= MIN_REWRITE_CJK_CHARS and not is_script_polluted(text):
        return text
    topic_text = topic or "这个热点"
    styles = [
        (
            f"你有没有发现，{topic_text}真正抓人的不是事件本身，而是它背后的反常识线索。"
            "先把悬念抛给观众，再补一个关键判断，让大家知道为什么现在值得看懂。"
        ),
        (
            f"如果你经常追热点却不知道怎么做内容，{topic_text}可以换成一个普通人视角。"
            "先说大家最容易忽略的痛点，再把影响讲明白，最后给一个能马上复用的表达角度。"
        ),
        (
            f"{topic_text}最值得关注的是机会信号。"
            "表面看是一个新闻点，往深一层看，是注意力、产业变化和内容选题之间的连接。"
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
    return f"{opening}这类内容好用的地方，是既能承接热点流量，也能展示你的专业判断。{_pipeline_cta(index)}"


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
        f"如果只用一句话拆{topic}，我会提醒你别只看标题。真正重要的是它背后的反差、线索和后续变化，这些才是观众愿意听完并继续互动的原因。",
    ]
    if transcript and len(samples[-1]) < 30:
        samples[-1] = transcript[:180]
    return [
        {"title": title, "script": _expand_pipeline_rewrite(script, topic=topic, template=template, title=title, index=index)}
        for index, (title, script) in enumerate(zip(REWRITE_TITLES, samples, strict=False))
    ]


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
        limit=9,
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
            "避免承诺绝对收益",
            "每个版本都要有明确口播节奏",
            "每个版本必须使用不同角度：悬念揭秘、用户痛点、机会提醒、老板视角、知识分享、故事版、直播口吻、极简强钩子、成交转化等",
            "每条文案开头和结尾不能重复，CTA 不能完全相同",
            "同一批文案中“下一条继续拆”最多出现 1 次，“先收藏”最多出现 1 次，不要每条都以“关注我”结尾",
            "不要重复“普通人看结果，懂内容的人会先问”这类固定句式",
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
