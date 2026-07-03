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
from app.services.viral_analyzer import (
    FINAL_REWRITE_LIMIT,
    analyze_viral_script,
    bound_script_to_source,
    dedupe_and_diversify_rewrites,
    is_surface_only_script,
    is_script_polluted,
    known_source_themes,
    natural_source_clause,
    normalize_source_video_core,
    source_detail_theme,
    source_opportunity_clause,
    source_theme_domain,
    smooth_spoken_script,
    source_core_brief,
)


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
        "source_video_core": analysis.get("source_video_core", {}),
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
    "后面如果这个方向继续有新变化，我会再单独拆给你看。",
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


def _spoken_clause(text: str) -> str:
    return natural_source_clause(text)


def _expand_pipeline_rewrite(
    script: str,
    *,
    topic: str,
    template: str,
    title: str,
    source_core: dict[str, Any] | None = None,
    transcript: str = "",
    index: int = 0,
) -> str:
    text = smooth_spoken_script(bound_script_to_source(script, source_core, transcript=transcript, topic=topic, template=template))
    if _cjk_len(text) >= MIN_REWRITE_CJK_CHARS and not is_script_polluted(text) and not is_surface_only_script(text, source_core, transcript=transcript, topic=topic, template=template):
        return text
    topic_text = topic or "这个热点"
    core = normalize_source_video_core(source_core or {}, transcript=transcript, topic=topic_text, template=template)
    core_event = natural_source_clause(str(core.get("core_event") or topic_text))
    core_conflict = natural_source_clause(str(core.get("core_conflict") or source_core_brief(source_core or {}, topic=topic_text)))
    causal_chain = natural_source_clause(str(core.get("causal_chain") or core_conflict))
    business_implication = natural_source_clause(str(core.get("business_implication") or core_conflict))
    audience_takeaway = natural_source_clause(str(core.get("audience_takeaway") or business_implication))
    detail_theme = source_detail_theme(source_core, transcript=transcript, topic=topic_text, template=template)
    opportunity_clause = source_opportunity_clause(source_core, transcript=transcript, topic=topic_text, template=template)
    domain = source_theme_domain(source_core, transcript=transcript, topic=topic_text, template=template)
    suspense_tail = "这些压力一旦被放大，供应链和产业链里的风险机会才是重点。" if domain == "supply_chain" else f"{detail_theme}一旦被放大，观众要看的就是用户需求和转化机会。"
    styles = [
        (
            f"你以为{topic_text}只是在聊消息真假？其实更该往下看。"
            f"表面是{core_event}，背后是{core_conflict}。"
            + suspense_tail
        ),
        (
            f"如果你经常追{topic_text}这种热点，最容易踩的坑就是只看标题。"
            f"更该注意的是{audience_takeaway}。"
            f"把{detail_theme}说清楚，观众才知道该关注哪里。"
        ),
        (
            f"从商业角度看，{topic_text}不能只当成一条消息刷过去。"
            f"更值得看的是{business_implication}。"
            f"{opportunity_clause}。"
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
    opening = text or bound_script_to_source(styles[index % len(styles)], source_core, transcript=transcript, topic=topic, template=template)
    return _append_pipeline_cta(opening, index)


def _fallback_rewrites(analysis: dict[str, Any], transcript: str) -> list[dict[str, str]]:
    topic = str(analysis.get("topic") or "这个爆款视频").strip()
    template = str(analysis.get("template") or "先提出问题，再给出解决方法，最后明确行动。").strip()
    source_core = normalize_source_video_core(
        analysis.get("source_video_core") or analysis.get("sourceVideoCore"),
        transcript=transcript,
        topic=topic,
        hook=str(analysis.get("hook") or ""),
        template=template,
    )
    core_event = natural_source_clause(str(source_core.get("core_event") or topic))
    core_conflict = _spoken_clause(str(source_core.get("core_conflict") or str(analysis.get("hook") or topic)))
    causal_chain = _spoken_clause(str(source_core.get("causal_chain") or core_conflict))
    business_implication = natural_source_clause(str(source_core.get("business_implication") or template))
    audience_takeaway = natural_source_clause(str(source_core.get("audience_takeaway") or business_implication))
    detail_theme = source_detail_theme(source_core, transcript=transcript, topic=topic, template=template)
    opportunity_clause = source_opportunity_clause(source_core, transcript=transcript, topic=topic, template=template)
    domain = source_theme_domain(source_core, transcript=transcript, topic=topic, template=template)
    pressure_tail = f"这些压力一旦被放大，重点就变成{audience_takeaway}" if domain == "supply_chain" else f"{detail_theme}一旦被放大，重点就变成用户需求和转化机会"
    samples = [
        f"今天换个更好懂的角度，聊聊{topic}。表面看是{core_event}，往下看是{core_conflict}。{pressure_tail}。",
        f"很多人看见{topic}就只看标题，但这样很容易错过后面的重点。更该注意的是{audience_takeaway}。先把{detail_theme}说清楚，观众才知道该关注哪里。",
        f"如果你从商业角度看{topic}，重点不是复述消息，而是看{business_implication}。{opportunity_clause}。",
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
        {"title": title, "script": _expand_pipeline_rewrite(script, topic=topic, template=template, title=title, source_core=source_core, transcript=transcript, index=index)}
        for index, (title, script) in enumerate(zip(REWRITE_TITLES, samples, strict=False))
    ]
    return dedupe_and_diversify_rewrites(
        rewrites,
        topic=topic,
        hook=str(analysis.get("hook") or "先用一个反差问题抓住注意力。"),
        template=template,
        language="zh",
        source_core=source_core,
        limit=FINAL_REWRITE_LIMIT,
    )


def _normalize_rewrites(value: Any, analysis: dict[str, Any], transcript: str) -> list[dict[str, str]]:
    fallback = _fallback_rewrites(analysis, transcript)
    source_core = normalize_source_video_core(
        analysis.get("source_video_core") or analysis.get("sourceVideoCore"),
        transcript=transcript,
        topic=str(analysis.get("topic") or "这个爆款视频"),
        hook=str(analysis.get("hook") or ""),
        template=str(analysis.get("template") or ""),
    )
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
                normalized.append({"title": title, "script": _expand_pipeline_rewrite(script, topic=str(analysis.get("topic") or "这个爆款视频"), template=str(analysis.get("template") or ""), title=title, source_core=source_core, transcript=transcript, index=len(normalized))})
            continue
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or item.get("version") or "").strip()
        script = str(item.get("script") or item.get("content") or item.get("text") or item.get("copy") or "").strip()
        if title and script:
            normalized.append({"title": title, "script": _expand_pipeline_rewrite(script, topic=str(analysis.get("topic") or "这个爆款视频"), template=str(analysis.get("template") or ""), title=title, source_core=source_core, transcript=transcript, index=len(normalized))})
    existing = {item["title"] for item in normalized}
    normalized.extend(item for item in fallback if item["title"] not in existing)
    return dedupe_and_diversify_rewrites(
        normalized,
        topic=str(analysis.get("topic") or "这个爆款视频"),
        hook=str(analysis.get("hook") or "先用一个反差问题抓住注意力。"),
        template=str(analysis.get("template") or ""),
        language="zh",
        source_core=source_core,
        limit=FINAL_REWRITE_LIMIT,
    )


async def _generate_nine_rewrites(*, transcript: str, analysis: dict[str, Any], language: str) -> list[dict[str, str]]:
    source_core = normalize_source_video_core(
        analysis.get("source_video_core") or analysis.get("sourceVideoCore"),
        transcript=transcript,
        topic=str(analysis.get("topic") or ""),
        hook=str(analysis.get("hook") or ""),
        template=str(analysis.get("template") or ""),
    )
    payload = {
        "language": LANGUAGE_LABELS.get(language, "中文"),
        "transcript": transcript,
        "analysis": _analysis_payload(analysis),
        "source_video_core": source_core,
        "rewrite_titles": REWRITE_TITLES,
        "requirements": [
            "不要逐字复制原文案",
            "必须是原创表达",
            "适合数字人口播",
            "必须先围绕 source_video_core 改写，不能只围绕标题或表层热点发挥",
            "必须保留原视频的核心事件、核心矛盾、关键因果链、行业/商业判断和观众应该关注的重点",
            "最终文案只能使用 transcript、metadata、analysis 和 source_video_core 已有信息，不能新增没有来源支撑的具体事实、实体、供应链环节或投资判断",
            "如果 transcript、metadata、analysis 或 source_video_core 已经出现“供应链、产业链、风险、机会、技术依赖、关键材料、产能、成本压力”等主题，最终 script 必须保留这些已知主题",
            "如果当前来源没有供应链、产业链、关键材料、技术依赖、产能、成本压力，不得把这些词写进最终 script",
            "电商/带货/情感共鸣/消费者心理类内容应围绕情感共鸣、用户需求、信任、内容转化、品牌表达和情绪价值，不要套用产业链话术",
            "不要因为保守而退回只讲招股书缺失、官方文件空白、信息真假或市场猜测",
            "如果来源没有明确出现，不要写政府合同、私人融资、不锈钢壳、发动机、地面设施等具体环节",
            "没有来源支撑的推测必须保守表达，可以用“可能、值得关注、需要进一步验证、观察角度”，不要写成确定事实",
            "禁止过度确定判断，例如“未来的金矿、一定受益、根本不需要上市、必然影响、确定机会”",
            "禁止箭头链条表达，例如“上市传闻→招股书未披露→市场猜测”，也不要写“差异分析、实质性进展待确认、市场猜测和不确定性、正式文件最靠谱”等报告腔",
            "最终 script 是直接展示给用户的口播稿，禁止出现“原视频、这个视频、视频里、这条视频、原文、素材、文案主线、主线是、想提醒的是、不是停在”等说明参考来源的词",
            "不要使用箭头链条表达，例如 A → B → C",
            "不要写成研究报告摘要，要像真人直接对镜头讲",
            "版本A的反差来自原视频内部矛盾，不要歪成单纯真假消息、标题党或辟谣",
            "版本B必须把用户痛点绑定原视频主线，说明只看标题会错过什么风险或机会",
            "版本C必须体现原视频里的商业机会；供应链类才写产业链机会，电商内容类写用户信任、情绪价值、内容转化或品牌表达",
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
