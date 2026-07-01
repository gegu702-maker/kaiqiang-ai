from __future__ import annotations

from datetime import UTC, datetime
from difflib import SequenceMatcher
import re
from typing import Any

from fastapi import HTTPException
from postgrest.exceptions import APIError
from supabase import Client

from app.services.billing import current_period_start, ensure_profile
from app.services.llm_provider import LLMProvider

INDUSTRY_LABELS = {
    "ecommerce": "电商带货",
    "knowledge": "知识口播",
    "training": "企业培训",
    "local": "本地生活",
    "personal_brand": "个人IP",
    "global": "出海营销",
}

LANGUAGE_LABELS = {
    "zh": "中文",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "ru": "Russian",
}

PLAN_LIMITS: dict[str, int | None] = {
    "free": 5,
    "plus": 100,
    "pro": 300,
    "business": None,
}

MIN_REWRITE_CJK_CHARS = 80
MIN_REWRITE_COUNT = 3
MIN_SELLING_POINTS = 4
MIN_STRUCTURE_ITEMS = 5
SOURCE_CORE_FIELDS = (
    "core_event",
    "core_conflict",
    "key_entities",
    "causal_chain",
    "business_implication",
    "audience_takeaway",
)
POLLUTION_PATTERNS = (
    "可复用模板",
    "可套用模板",
    "模板是",
    "结构是",
    "这个版本适合",
    "建议用户",
    "分析如下",
    "字段",
    "JSON",
    "+（",
    "+【",
    "（开头",
    "（痛点",
    "（行动号召",
    "【热点事件】",
)
SCRIPT_PREFIX_RE = re.compile(r"^\s*(?:script|文案|口播文案|正文|版本[A-ZＡ-Ｚ]?)\s*[:：]\s*", re.IGNORECASE)
TEMPLATE_BLOCK_RE = re.compile(
    r"(?:可复用模板是|可套用模板是|模板是|该版本的模板|这个版本适合|建议用户|分析：|结构：|可套用模板：|可复用模板：).*",
    re.DOTALL,
)
BRACKET_TEMPLATE_RE = re.compile(r"(?:[（(【\\[][^）)】\\]]{0,24}(?:开头|热点事件|痛点|行动号召|信息增量|案例|类比)[^）)】\\]]*[）)】\\]]\s*\+?)+")
COMMON_CTA_RE = re.compile(
    r"(?:如果你也想看懂这类热点，?)?(?:先收藏，?)?下一条继续拆(?:给你看)?[。！!]*|"
    r"关注我，?下一条继续拆(?:给你看)?[。！!]*|"
    r"先收藏，?下次判断热点时再看[。！!]*|"
    r"先收藏[。！!]*|"
    r"你觉得(?:真正)?的?重点在哪里？评论区说说你的判断[。！!]*|"
    r"如果你也在做内容，把这个拆法先记下来，下一次热点就能直接套用[。！!]*|"
    r"后面如果产业链继续有新变化，我会再单独拆给你看[。！!]*"
)
SCRIPT_PUNCT_RE = re.compile(r"[\s，。！？、；：,.!?;:\"'“”‘’（）()\[\]【】《》<>-]+")

FINAL_REWRITE_LIMIT = 3
REWRITE_STRATEGIES = [
    {
        "title": "版本A：热点反差版",
        "style": "suspense",
        "opening": "反常识开头",
        "logic": "信息差",
        "ending": "观点讨论",
        "cta": "你觉得真正的重点在哪里？评论区说说你的判断。",
    },
    {
        "title": "版本B：用户痛点版",
        "style": "pain_point",
        "opening": "朋友提醒开头",
        "logic": "内容创作方法",
        "ending": "行动建议",
        "cta": "如果你也在做内容，把这个拆法先记下来，下一次热点就能直接套用。",
    },
    {
        "title": "版本C：商业机会版",
        "style": "opportunity",
        "opening": "老板视角开头",
        "logic": "供应链机会",
        "ending": "行业后续",
        "cta": "后面如果产业链继续有新变化，我会再单独拆给你看。",
    },
    {
        "title": "版本D：故事口吻版",
        "style": "story",
        "opening": "故事开头",
        "logic": "认知升级",
        "ending": "转发提醒",
        "cta": "把这条转给那个总爱只看热闹的朋友，让他也换个角度看。",
    },
    {
        "title": "版本E：直播互动版",
        "style": "live_stream",
        "opening": "直播开头",
        "logic": "风险提醒",
        "ending": "留言互动",
        "cta": "你想让我从哪个行业继续拆？直接把方向打在评论里。",
    },
]
CTA_POOL = [str(item["cta"]) for item in REWRITE_STRATEGIES]
STYLE_KEYS = [str(item["style"]) for item in REWRITE_STRATEGIES]
OVERUSED_PHRASE_BUCKETS = [
    ("generic_value", ("这类内容好用的地方", "承接热点流量", "展示你的专业判断")),
    ("surface_heat", ("真正值得关注的不是表面的热闹", "不是表面的热闹")),
    ("ordinary_people", ("普通人看结果", "懂内容的人会先问")),
    ("valuable_judgement", ("把这个问题讲清楚，再补充一个有价值的判断",)),
    ("continue_comment", ("想看我继续拆这个方向", "评论区留一个", "留一个“继续”", "留一个继续")),
    ("opportunity_risk", ("这背后是机会还是风险",)),
    ("save_later", ("先收藏", "下次判断热点时再看")),
    ("dont_follow", ("别急着跟风",)),
    ("detail_chance", ("机会藏在细节里",)),
    ("listing_news", ("别只盯着上市新闻",)),
]
AWKWARD_SPOKEN_REPLACEMENTS = (
    ("真正值得关注的不是表面的热闹", "别只看表面的热闹"),
    ("真正值得学习的，不只是", "别只学"),
    ("真正要看的，是", "更值得看的，是"),
    ("真正抓人的地方，是", "更抓人的地方在于"),
    ("它会先制造一个疑问：", "你可以先抛出一个问题："),
    ("行动号召", "下一步动作"),
    ("信息价值", "有用信息"),
    ("模板说明", ""),
    ("值得学习的是", "可以借鉴的是"),
    ("先别急着模仿表面内容", "别先忙着照搬标题"),
    ("结构", "节奏"),
    ("你觉得的重点", "你觉得重点"),
    ("原视频的主线是", ""),
    ("原视频想提醒的是", ""),
    ("原视频更想提醒的是", ""),
    ("原视频不是", ""),
    ("这个视频", "这件事"),
    ("视频里", "内容里"),
    ("这条视频", "这条内容"),
    ("原视频", ""),
    ("原文", ""),
    ("素材", ""),
    ("文案主线", "重点"),
    ("主线是", "重点是"),
    ("想提醒的是", "要注意的是"),
    ("不是停在", "别只看"),
)
UNSUPPORTED_FACT_PHRASES = (
    "政府合同",
    "私人融资",
    "不锈钢壳",
    "发动机",
    "地面设施",
)
OVERCONFIDENT_FACT_REPLACEMENTS = (
    ("根本不需要上市", "不能只看上市传闻"),
    ("未来的金矿", "值得关注的机会"),
    ("一定受益", "可能受益"),
    ("必然影响", "可能影响"),
    ("确定机会", "值得关注的机会"),
    ("技术壁垒", "技术依赖"),
    ("vs.", "和"),
)
KNOWN_THEME_TERMS = (
    "供应链",
    "产业链",
    "风险",
    "机会",
    "技术依赖",
    "关键材料",
    "产能",
    "成本压力",
)
SURFACE_ONLY_PHRASES = (
    "招股书缺失",
    "正式文件最靠谱",
    "官方文件空白",
    "信息真假",
    "市场猜测",
)
REPORT_TONE_REPLACEMENTS = (
    ("差异分析", "换个角度看"),
    ("实质性进展待确认", "还需要继续观察"),
    ("市场猜测和不确定性", "供应链和产业链里的风险机会"),
    ("正式文件最靠谱", "别只看文件进度"),
    ("官方文件空白", "公开信息还不够完整"),
)


def _count_monthly_analyses(supabase: Client, *, user_id: str) -> int:
    try:
        result = (
            supabase.table("usage_logs")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("action", "viral_analyze")
            .gte("created_at", current_period_start())
            .execute()
        )
        return result.count or 0
    except APIError:
        return 0


def _assert_viral_quota(supabase: Client, *, user_id: str, email: str) -> dict[str, Any]:
    profile = ensure_profile(supabase, user_id=user_id, email=email)
    plan = profile.get("plan") or "free"
    limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    used = _count_monthly_analyses(supabase, user_id=user_id)
    if limit is not None and used >= limit:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "viral_analyze_quota_exceeded",
                "message": "本月爆款拆解次数已用完，请升级套餐。",
                "plan": plan,
                "used": used,
                "monthly_limit": limit,
            },
        )
    return {"plan": plan, "used": used, "monthly_limit": limit}


def _list_of_strings(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or fallback
    if isinstance(value, str):
        parts = [
            item.strip(" -•\t")
            for item in value.replace("；", "\n").replace(";", "\n").replace("、", "\n").replace("/", "\n").splitlines()
            if item.strip(" -•\t")
        ]
        return parts or ([value.strip()] if value.strip() else fallback)
    return fallback


def _split_source_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return []
    parts = re.split(r"[。！？!?；;\n]+", normalized)
    return [part.strip(" ：:，,。；;") for part in parts if part.strip(" ：:，,。；;")]


def _pick_source_sentence(sentences: list[str], terms: tuple[str, ...], fallback: str) -> str:
    for sentence in sentences:
        if any(term in sentence for term in terms):
            return sentence
    return fallback


def _extract_key_entities(text: str) -> list[str]:
    entities: list[str] = []
    known_terms = (
        "SpaceX",
        "纳斯达克",
        "供应链",
        "产业链",
        "关键材料",
        "技术量产",
        "地缘政治",
        "AI",
        "特斯拉",
        "马斯克",
    )
    for term in known_terms:
        if term in text and term not in entities:
            entities.append(term)
    for match in re.findall(r"[A-Za-z][A-Za-z0-9.&+-]{1,}", text):
        if match not in entities:
            entities.append(match)
    return entities[:8]


def normalize_source_video_core(value: Any, *, transcript: str = "", topic: str = "", hook: str = "", template: str = "") -> dict[str, Any]:
    source_text = "\n".join(str(part or "") for part in (topic, hook, template, transcript)).strip()
    sentences = _split_source_sentences(source_text)
    fallback_topic = topic or "这个视频"

    if not isinstance(value, dict):
        value = {}

    core_event = str(value.get("core_event") or "").strip() or _pick_source_sentence(
        sentences,
        ("上市", "传闻", "消息", "发布", "融资", "纳斯达克", "招股书", "SpaceX"),
        fallback_topic,
    )
    core_conflict = str(value.get("core_conflict") or "").strip() or _pick_source_sentence(
        sentences,
        ("风险", "矛盾", "卡住", "限制", "真假", "供应链", "地缘政治", "量产"),
        hook or core_event,
    )
    causal_chain = str(value.get("causal_chain") or "").strip() or _pick_source_sentence(
        sentences,
        ("因为", "导致", "带来", "影响", "如果", "一旦", "供应链", "技术量产"),
        core_conflict,
    )
    business_implication = str(value.get("business_implication") or "").strip() or _pick_source_sentence(
        sentences,
        ("机会", "产业链", "供应链", "商业", "材料", "量产", "订单", "公司"),
        template or core_conflict,
    )
    audience_takeaway = str(value.get("audience_takeaway") or "").strip() or _pick_source_sentence(
        sentences,
        ("关注", "重点", "别只看", "风险", "机会", "判断"),
        business_implication or core_conflict,
    )
    key_entities = _list_of_strings(value.get("key_entities"), _extract_key_entities(source_text))
    return {
        "core_event": core_event,
        "core_conflict": core_conflict,
        "key_entities": key_entities,
        "causal_chain": causal_chain,
        "business_implication": business_implication,
        "audience_takeaway": audience_takeaway,
    }


def source_core_brief(source_core: dict[str, Any], *, topic: str = "") -> str:
    core = normalize_source_video_core(source_core, topic=topic)
    entities = "、".join(_list_of_strings(core.get("key_entities"), []))
    parts = [
        str(core.get("core_event") or topic or "").strip(),
        str(core.get("core_conflict") or "").strip(),
        str(core.get("causal_chain") or "").strip(),
        str(core.get("business_implication") or "").strip(),
        str(core.get("audience_takeaway") or "").strip(),
        entities,
    ]
    return smooth_spoken_script("。".join(part for part in parts if part))


def _source_support_text(
    source_core: dict[str, Any] | None,
    *,
    transcript: str = "",
    topic: str = "",
    hook: str = "",
    template: str = "",
) -> str:
    core = normalize_source_video_core(source_core or {}, transcript=transcript, topic=topic, hook=hook, template=template)
    parts: list[str] = [transcript, topic, hook, template]
    for value in core.values():
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value or ""))
    return "\n".join(part for part in parts if part)


def known_source_themes(
    source_core: dict[str, Any] | None,
    *,
    transcript: str = "",
    topic: str = "",
    hook: str = "",
    template: str = "",
) -> list[str]:
    support_text = _source_support_text(source_core, transcript=transcript, topic=topic, hook=hook, template=template)
    return [term for term in KNOWN_THEME_TERMS if term in support_text]


def script_preserves_known_themes(
    script: str,
    source_core: dict[str, Any] | None,
    *,
    transcript: str = "",
    topic: str = "",
    hook: str = "",
    template: str = "",
) -> bool:
    themes = known_source_themes(source_core, transcript=transcript, topic=topic, hook=hook, template=template)
    if not themes:
        return True
    text = str(script or "")
    has_chain = not any(term in themes for term in ("供应链", "产业链")) or any(term in text for term in ("供应链", "产业链"))
    has_risk_or_opportunity = not any(term in themes for term in ("风险", "机会")) or any(term in text for term in ("风险", "机会"))
    specific_theme_hits = sum(1 for term in themes if term in text)
    return has_chain and has_risk_or_opportunity and specific_theme_hits >= min(3, len(themes))


def is_surface_only_script(
    script: str,
    source_core: dict[str, Any] | None,
    *,
    transcript: str = "",
    topic: str = "",
    hook: str = "",
    template: str = "",
) -> bool:
    text = str(script or "")
    has_report_tone = any(phrase in text for phrase in (*SURFACE_ONLY_PHRASES, "差异分析", "实质性进展待确认", "正式文件最靠谱", "官方文件空白"))
    has_arrow_chain = "→" in text or "->" in text or bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9]—[\u4e00-\u9fffA-Za-z0-9]", text))
    return has_arrow_chain or has_report_tone or not script_preserves_known_themes(
        text,
        source_core,
        transcript=transcript,
        topic=topic,
        hook=hook,
        template=template,
    )


def _drop_unsupported_fact_sentences(text: str, unsupported_phrases: tuple[str, ...]) -> str:
    if not unsupported_phrases:
        return text
    parts = re.split(r"([。！？!?；;])", text)
    kept: list[str] = []
    for index in range(0, len(parts), 2):
        sentence = parts[index]
        punct = parts[index + 1] if index + 1 < len(parts) else ""
        if sentence and any(phrase in sentence for phrase in unsupported_phrases):
            continue
        kept.append(f"{sentence}{punct}")
    cleaned = "".join(kept).strip()
    if cleaned:
        return cleaned
    value = text
    for phrase in unsupported_phrases:
        value = value.replace(phrase, "")
    return value


def bound_script_to_source(
    script: str,
    source_core: dict[str, Any] | None = None,
    *,
    transcript: str = "",
    topic: str = "",
    hook: str = "",
    template: str = "",
) -> str:
    text = str(script or "")
    if not text:
        return ""
    support_text = _source_support_text(source_core, transcript=transcript, topic=topic, hook=hook, template=template)
    for source, target in OVERCONFIDENT_FACT_REPLACEMENTS:
        if source not in support_text:
            text = text.replace(source, target)
    for source, target in REPORT_TONE_REPLACEMENTS:
        text = text.replace(source, target)
    text = text.replace("→", "，").replace("->", "，")
    text = re.sub(r"(?<=[\u4e00-\u9fffA-Za-z0-9])—(?=[\u4e00-\u9fffA-Za-z0-9])", "，", text)
    unsupported = tuple(phrase for phrase in UNSUPPORTED_FACT_PHRASES if phrase in text and phrase not in support_text)
    text = _drop_unsupported_fact_sentences(text, unsupported)
    text = re.sub(r"[，,]\s*[，,。；;]", "，", text)
    text = re.sub(r"。{2,}", "。", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ：:，,。；; ")


def _source_core_terms(source_core: dict[str, Any] | None) -> list[str]:
    if not source_core:
        return []
    core = normalize_source_video_core(source_core)
    terms: list[str] = []
    for value in core.values():
        if isinstance(value, list):
            candidates = value
        else:
            candidates = re.split(r"[，。！？、；：\s/]+", str(value or ""))
        for candidate in candidates:
            text = str(candidate).strip()
            if len(text) >= 2 and text not in terms:
                terms.append(text)
    return terms[:16]


def _script_matches_source_core(script: str, source_core: dict[str, Any] | None) -> bool:
    terms = _source_core_terms(source_core)
    if not terms:
        return True
    hits = sum(1 for term in terms if term in script)
    return hits >= min(3, len(terms))


def _cjk_len(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


def sanitize_rewrite_script(script: str) -> str:
    text = str(script or "").strip()
    text = SCRIPT_PREFIX_RE.sub("", text)
    text = TEMPLATE_BLOCK_RE.sub("", text)
    text = BRACKET_TEMPLATE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ：:，,。；;")


def _with_sentence_end(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    if value[-1] in "。！？!?":
        return value
    return f"{value}。"


def _join_sentences(*parts: str) -> str:
    return "".join(_with_sentence_end(part) for part in parts if str(part or "").strip()).strip()


def smooth_spoken_script(script: str) -> str:
    text = sanitize_rewrite_script(script)
    for source, target in AWKWARD_SPOKEN_REPLACEMENTS:
        text = text.replace(source, target)
    text = re.sub(r"真正", "", text)
    text = text.replace("你觉得的重点", "你觉得重点")
    text = re.sub(r"这条\s*的", "这条内容的", text)
    text = re.sub(r"从([^。！？!?]{2,40})讲到", r"先看\1，再看", text)
    text = re.sub(r"(互动)(你觉得|评论区)", r"\1。\2", text)
    text = re.sub(r"(判断|套用|看)(\s+)(我更想提醒|如果你也在做内容|后面如果)", r"\1。\3", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([。！？!?])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ：:，,。；;")


def natural_source_clause(text: str) -> str:
    value = smooth_spoken_script(text)
    value = re.sub(r"^表面(?:看)?是[^，。！？!?]+[，,](?:往下看才是|背后是|后面是|其实是)", "", value)
    value = re.sub(r"^如果\s*", "", value)
    value = re.sub(r"^一旦\s*", "", value)
    return value.strip(" ：:，,。；; ")


def is_script_polluted(script: str) -> bool:
    text = str(script or "")
    return any(pattern in text for pattern in POLLUTION_PATTERNS) or bool(BRACKET_TEMPLATE_RE.search(text))


def _normalize_for_similarity(text: str) -> str:
    return SCRIPT_PUNCT_RE.sub("", str(text or "")).lower()


def rewrite_similarity(left: str, right: str) -> float:
    a = _normalize_for_similarity(left)
    b = _normalize_for_similarity(right)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _strategy_for_index(index: int) -> dict[str, str]:
    strategy = REWRITE_STRATEGIES[index % len(REWRITE_STRATEGIES)]
    return {key: str(value) for key, value in strategy.items()}


def _style_for_index(index: int, title: str = "") -> str:
    title_text = str(title or "")
    if any(key in title_text for key in ("痛点", "普通人")):
        return "pain_point"
    if any(key in title_text for key in ("机会", "行动", "转化", "成交")):
        return "opportunity"
    if any(key in title_text for key in ("老板", "创业")):
        return "boss_view"
    if "知识" in title_text:
        return "knowledge"
    if "故事" in title_text:
        return "story"
    if "直播" in title_text:
        return "live_stream"
    if "极简" in title_text:
        return "minimal"
    return _strategy_for_index(index)["style"]


def _cta_for_index(index: int) -> str:
    return _strategy_for_index(index)["cta"]


def _phrase_buckets(script: str) -> set[str]:
    text = str(script or "")
    buckets: set[str] = set()
    for bucket, phrases in OVERUSED_PHRASE_BUCKETS:
        if any(phrase in text for phrase in phrases):
            buckets.add(bucket)
    return buckets


def extract_script_signature(script: str) -> str:
    text = str(script or "")
    if any(word in text[:45] for word in ("家人们", "直播间", "别划走")):
        opening = "直播开头"
    elif any(word in text[:60] for word in ("朋友", "昨天", "有人问")):
        opening = "故事开头"
    elif any(word in text[:60] for word in ("你有没有发现", "你以为", "不是")):
        opening = "反常识开头"
    elif "如果你是老板" in text[:80]:
        opening = "老板视角开头"
    elif any(word in text[:60] for word in ("如果你", "很多人做内容", "经常看热点", "第一反应就是复述")):
        opening = "朋友提醒开头"
    elif any(word in text[:80] for word in ("老板", "创业者", "产业链", "供应链")):
        opening = "老板视角开头"
    elif any(word in text[:60] for word in ("怎么", "拆成", "讲成")):
        opening = "教学开头"
    else:
        opening = "新闻播报开头"

    if any(word in text for word in ("做内容", "选题", "涨粉", "口播", "拆法", "能拍", "互动的角度")):
        logic = "内容创作方法"
    elif any(word in text for word in ("没说", "隐藏", "线索没有被明说", "信息差", "反差")):
        logic = "信息差"
    elif any(word in text for word in ("供应链", "产业链", "招股书", "商业", "供应关系")):
        logic = "供应链机会"
    elif any(word in text for word in ("风险", "别急", "先别")):
        logic = "风险提醒"
    elif any(word in text for word in ("机会", "红利", "变化")):
        logic = "投资机会"
    elif any(word in text for word in ("普通人", "痛点", "错过")):
        logic = "用户痛点"
    else:
        logic = "认知升级"

    tail = text[-60:]
    if any(word in tail for word in ("评论", "聊聊", "判断")):
        ending = "观点讨论"
    elif any(word in tail for word in ("收藏", "记下来", "套用")):
        ending = "行动建议"
    elif any(word in tail for word in ("关注", "后续", "新变化")):
        ending = "行业后续"
    elif any(word in tail for word in ("转给", "朋友")):
        ending = "转发提醒"
    elif any(word in tail for word in ("方向打在", "留言")):
        ending = "留言互动"
    else:
        ending = "行动建议"
    return f"{opening}|{logic}|{ending}"


def _trim_common_cta(script: str) -> str:
    text = COMMON_CTA_RE.sub("", str(script or ""))
    for cta in CTA_POOL:
        text = text.replace(cta, "")
        text = text.replace(cta.rstrip("。！？!"), "")
    return re.sub(r"\s+", " ", text).strip(" ，。！？；;")


def _script_with_unique_cta(script: str, index: int) -> str:
    text = smooth_spoken_script(_trim_common_cta(script))
    cta = _cta_for_index(index)
    if cta in text:
        return smooth_spoken_script(text)
    return smooth_spoken_script(_join_sentences(text, cta))


def _compose_diverse_script(
    *,
    topic: str,
    hook: str,
    template: str,
    language: str,
    style: str,
    seed: str,
    index: int,
    source_core: dict[str, Any] | None = None,
) -> str:
    strategy = _strategy_for_index(index)
    if language != "zh":
        base = (
            f"{seed or hook or topic} Start from a clear contrast, explain why {topic} matters, "
            "turn the point into one practical takeaway, and close with a viewer action that differs from the other versions."
        )
        return base.strip()

    topic_text = topic or "这个热点"
    core = normalize_source_video_core(source_core or {}, transcript=seed, topic=topic, hook=hook, template=template)
    core_event = smooth_spoken_script(str(core.get("core_event") or topic_text))
    core_conflict = natural_source_clause(str(core.get("core_conflict") or hook or core_event))
    causal_chain = natural_source_clause(str(core.get("causal_chain") or core_conflict))
    business_implication = natural_source_clause(str(core.get("business_implication") or template or core_conflict))
    audience_takeaway = natural_source_clause(str(core.get("audience_takeaway") or business_implication))
    support_text = _source_support_text(core, transcript=seed, topic=topic, hook=hook, template=template)
    detail_theme = next(
        (term for term in ("关键材料", "技术量产", "技术依赖", "地缘政治", "产能", "成本压力") if term in support_text),
        "产业链变化",
    )
    hook_text = smooth_spoken_script(_trim_common_cta(seed)) or smooth_spoken_script(hook) or f"{topic_text}有一个容易被忽略的点。"
    lines = {
        "suspense": (
            f"你以为{topic_text}只是一个普通热点？先别急着下结论。"
            f"表面看是{core_event}，往下看才是{core_conflict}。"
            "这些压力一旦被放大，观众真正要判断的就是风险和机会。"
        ),
        "pain_point": (
            f"如果你只看{topic_text}的标题，很容易把重点看浅。"
            f"更该注意的是{audience_takeaway}。"
            f"你做内容时先把{detail_theme}这层产业链关系说清楚，再讲它怎么影响普通人的判断。"
        ),
        "opportunity": (
            f"如果你是老板或者行业观察者，{topic_text}别只当成一条新闻刷过去。"
            f"商业上更该看{business_implication}。"
            f"再看{detail_theme}带来的压力，哪一段产业链可能被重新关注，机会就会更清楚。"
        ),
        "boss_view": (
            f"站在经营者视角看，{topic_text}更像一道趋势题。"
            "别只看谁上了热搜，要看谁拿到了资源，谁靠近用户，谁可能改变原来的合作关系。"
            "这些位置一变，有准备的人就会先调整选题、产品和打法。"
        ),
        "knowledge": (
            f"想把{topic_text}讲成知识口播，可以简单一点。"
            "先说背景，再说矛盾，最后给一个判断方法。"
            "观众听完不只是知道一条消息，还能学会下次遇到类似热点该怎么看。"
        ),
        "story": (
            f"昨天有个朋友问我：{topic_text}这种事，和普通人到底有什么关系？"
            "我说，关系可能不在新闻本身，而在它提醒我们：很多机会一开始都藏在不起眼的小变化里。"
            "把这个转折讲出来，观众会更容易听进去。"
        ),
        "live_stream": (
            f"家人们，这个消息先别只看热闹，{topic_text}里面有一个很适合互动的点。"
            "我们先看谁被影响，再看谁可能受益，最后看你所在的行业能不能借这个话题做一条内容。"
        ),
        "minimal": (
            f"一句话拆{topic_text}：别只看结论，要看它为什么在这个时间点被讨论。"
            "开头用反差抓人，中间补一条关键信息，结尾给观众一个参与判断的理由。"
        ),
        "conversion": (
            f"如果你要把{topic_text}改成能带来咨询或转化的口播，先别堆信息。"
            "先指出观众正在错过什么，再给一个清晰判断，最后把下一步行动说得足够具体。"
        ),
    }
    body = lines.get(style, lines["suspense"])
    return smooth_spoken_script(
        bound_script_to_source(
            _join_sentences(body, strategy["cta"]),
            core,
            transcript=seed,
            topic=topic,
            hook=hook,
            template=template,
        )
    )


def _extend_unique(items: list[str], fallback: list[str], min_count: int) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in [*items, *fallback]:
        text = str(item).strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
        if len(normalized) >= min_count:
            break
    return normalized


def _expand_rewrite_script(
    script: str,
    *,
    topic: str,
    hook: str,
    template: str,
    language: str,
    variant: str,
    index: int = 0,
    source_core: dict[str, Any] | None = None,
) -> str:
    text = smooth_spoken_script(bound_script_to_source(script, source_core, topic=topic, hook=hook, template=template))
    style = _style_for_index(index, variant)
    if language != "zh":
        if len(text.split()) >= 70 and not is_script_polluted(text):
            return text
        return _compose_diverse_script(topic=topic, hook=hook, template=template, language=language, style=style, seed=text, index=index, source_core=source_core)
    if (
        _cjk_len(text) >= MIN_REWRITE_CJK_CHARS
        and not is_script_polluted(text)
        and _script_matches_source_core(text, source_core)
        and not is_surface_only_script(text, source_core, topic=topic, hook=hook, template=template)
    ):
        return _script_with_unique_cta(text, index)
    return _compose_diverse_script(topic=topic, hook=hook, template=template, language=language, style=style, seed=text, index=index, source_core=source_core)


def dedupe_and_diversify_rewrites(
    rewrites: list[dict[str, str]],
    *,
    topic: str,
    hook: str,
    template: str,
    language: str,
    source_core: dict[str, Any] | None = None,
    limit: int = FINAL_REWRITE_LIMIT,
) -> list[dict[str, str]]:
    diversified: list[dict[str, str]] = []
    seen_signatures: set[str] = set()
    for index, item in enumerate(rewrites):
        strategy = _strategy_for_index(index)
        incoming_title = str(item.get("title") or "").strip()
        title = strategy["title"] if language == "zh" and index < len(REWRITE_STRATEGIES) else incoming_title or f"Version {index + 1}"
        script = _expand_rewrite_script(
            str(item.get("script") or ""),
            topic=topic,
            hook=hook,
            template=template,
            language=language,
            variant=title,
            index=index,
            source_core=source_core,
        )
        signature = extract_script_signature(script)
        if (
            is_script_polluted(script)
            or _cjk_len(script) < MIN_REWRITE_CJK_CHARS
            or _phrase_buckets(script)
            or signature in seen_signatures
        ):
            script = _compose_diverse_script(
                topic=topic,
                hook=hook,
                template=template,
                language=language,
                style=strategy["style"],
                seed="",
                index=index,
                source_core=source_core,
            )
            signature = extract_script_signature(script)
        if any(rewrite_similarity(script, previous["script"]) > 0.60 for previous in diversified) or signature in seen_signatures:
            script = _compose_diverse_script(
                topic=topic,
                hook=hook,
                template=template,
                language=language,
                style=strategy["style"],
                seed="",
                index=index,
                source_core=source_core,
            )
            signature = extract_script_signature(script)
        diversified.append({"title": title, "script": script})
        seen_signatures.add(signature)
        if len(diversified) >= limit:
            break
    return diversified


def _default_rewrites(topic: str, hook: str, template: str, language: str, source_core: dict[str, Any] | None = None) -> list[dict[str, str]]:
    if language != "zh":
        base = [
            ("Version A: Steady analysis", f"{hook} The real value of this topic is not the headline itself, but the contrast behind it. Explain what changed, why it matters, what viewers can learn, and invite them to follow the next update."),
            ("Version B: Strong hook", f"Most people only see the surface of {topic}, but the more useful question is what signal it gives us. Start with the conflict, break down the clue, offer a practical interpretation, and end with a clear action."),
            ("Version C: Conversational", f"If you want to turn {topic} into a short video, do not simply repeat the news. Use one sharp question, one useful insight, one possible extension, and one simple call to action."),
        ]
        return [{"title": title, "script": script} for title, script in base]
    base = [
        (
            "版本A：稳健拆解版",
            f"{hook} 这条内容别只看{topic}本身，更要看事件、矛盾和后面的行业判断怎么连起来。先讲清核心事件，再讲因果链，观众才会知道该看风险还是机会。",
        ),
        (
            "版本B：强钩子口播版",
            f"很多人看到{topic}，第一反应就是照着讲一遍，但这样很难留下观众。你可以先问一句：只看标题会错过什么？再把风险、线索和影响讲清楚。",
        ),
        (
            "版本C：转化引导版",
            f"如果你也想做{topic}这类内容，别急着照搬标题。先说事件，再说矛盾，接着把商业判断讲出来，让观众知道哪条产业链可能有风险和机会。",
        ),
    ]
    return [
        {"title": title, "script": _expand_rewrite_script(script, topic=topic, hook=hook, template=template, language=language, variant=title, index=index, source_core=source_core)}
        for index, (title, script) in enumerate(base)
    ]


def _rewrites(value: Any, fallback_topic: str, language: str, *, hook: str = "", template: str = "", source_core: dict[str, Any] | None = None) -> list[dict[str, str]]:
    fallback_hook = hook or "先用一个反差问题抓住注意力。"
    fallback_template = template or "开头钩子 + 问题放大 + 信息价值 + 行动号召"
    default = _default_rewrites(fallback_topic, fallback_hook, fallback_template, language, source_core)
    if isinstance(value, str):
        value = [{"title": "基础版" if language == "zh" else "Base version", "script": value}]
    if not isinstance(value, list):
        return dedupe_and_diversify_rewrites(
            default,
            topic=fallback_topic,
            hook=fallback_hook,
            template=fallback_template,
            language=language,
            source_core=source_core,
            limit=FINAL_REWRITE_LIMIT,
        )
    normalized: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            script = item.strip()
            if script:
                normalized.append({"title": f"版本{len(normalized) + 1}" if language == "zh" else f"Version {len(normalized) + 1}", "script": script})
            continue
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or item.get("version") or "").strip()
        script = str(item.get("script") or item.get("content") or item.get("text") or item.get("copy") or "").strip()
        if title and script:
            normalized.append({"title": title, "script": script})
    if len(normalized) < MIN_REWRITE_COUNT:
        existing_titles = {item["title"] for item in normalized}
        normalized.extend([item for item in default if item["title"] not in existing_titles])
    return dedupe_and_diversify_rewrites(
        normalized[:MIN_REWRITE_COUNT],
        topic=fallback_topic,
        hook=fallback_hook,
        template=fallback_template,
        language=language,
        source_core=source_core,
        limit=FINAL_REWRITE_LIMIT,
    )


def validate_viral_analysis_payload(payload: dict[str, Any], *, language: str) -> dict[str, Any]:
    topic = str(payload.get("topic") or ("短视频内容拆解" if language == "zh" else "Short video content analysis")).strip()
    hook = str(payload.get("hook") or ("先用一个反差问题抓住注意力。" if language == "zh" else "Start with a contrast question.")).strip()
    template = str(
        payload.get("template")
        or payload.get("template_formula")
        or ("开头钩子 + 问题放大 + 信息价值 + 行动号召" if language == "zh" else "Hook + Problem + Value + CTA")
    ).strip()
    source_core = normalize_source_video_core(
        payload.get("source_video_core") or payload.get("sourceVideoCore"),
        transcript=str(payload.get("raw_script") or payload.get("transcript") or ""),
        topic=topic,
        hook=hook,
        template=template,
    )
    default_points = (
        ["热点自带关注", "反差制造好奇", "问题指向明确", "结尾便于互动"]
        if language == "zh"
        else ["Timely attention", "Contrast creates curiosity", "Clear problem", "Easy CTA"]
    )
    default_structure = (
        ["开头钩子：用反差或问题抓住注意力", "问题放大：说明为什么值得关注", "信息增量：补充关键线索", "证明/案例：用公开信息增强可信度", "行动号召：引导评论、收藏或继续关注"]
        if language == "zh"
        else ["Hook: create contrast", "Problem: explain why it matters", "Value: add key clues", "Proof: use public context", "CTA: invite the next action"]
    )
    selling_points = _extend_unique(_list_of_strings(payload.get("selling_points"), default_points), default_points, MIN_SELLING_POINTS)
    structure = _extend_unique(_list_of_strings(payload.get("structure"), default_structure), default_structure, MIN_STRUCTURE_ITEMS)
    rewrites_value = payload.get("rewrites")
    if rewrites_value is None:
        rewrites_value = payload.get("rewrite_versions") or payload.get("rewriteVersions") or payload.get("scripts")
    normalized_rewrites = _rewrites(rewrites_value, topic, language, hook=hook, template=template, source_core=source_core)
    return {
        "topic": topic,
        "hook": hook,
        "selling_points": selling_points,
        "structure": structure,
        "template": template,
        "source_video_core": source_core,
        "rewrites": normalized_rewrites,
    }


async def analyze_viral_script(
    supabase: Client,
    *,
    user_id: str,
    email: str,
    source_url: str = "",
    raw_script: str = "",
    industry: str,
    language: str,
) -> dict[str, Any]:
    source_url = source_url.strip()
    raw_script = raw_script.strip()
    if industry not in INDUSTRY_LABELS:
        raise HTTPException(status_code=400, detail="Invalid industry.")
    if language not in LANGUAGE_LABELS:
        raise HTTPException(status_code=400, detail="Invalid language.")
    if not source_url and not raw_script:
        raise HTTPException(status_code=400, detail="请至少粘贴短视频链接或原始视频文案。")
    if source_url and not raw_script:
        raise HTTPException(status_code=422, detail="暂时无法自动解析该链接，请粘贴视频文案或上传视频后补充文案。")
    if len(raw_script) > 6000:
        raise HTTPException(status_code=400, detail="原始文案过长，请控制在 6000 字以内。")

    quota = _assert_viral_quota(supabase, user_id=user_id, email=email)
    output_language = LANGUAGE_LABELS[language]
    fallback_text = {
        "topic": "短视频内容拆解" if language == "zh" else "Short video content analysis",
        "hook": "用强问题或反差在前 3 秒抓住注意力。" if language == "zh" else "Use a strong question or contrast to capture attention in the first 3 seconds.",
        "selling_points": ["痛点明确", "反差制造注意力", "好奇心推动完播", "利益点清晰", "情绪共鸣", "信任背书"]
        if language == "zh"
        else ["Clear pain point", "Contrast for attention", "Curiosity for completion", "Clear benefit", "Emotional resonance", "Trust proof"],
        "structure": ["开头钩子", "问题放大", "解决方案", "证明/案例", "行动号召"]
        if language == "zh"
        else ["Opening hook", "Amplify the problem", "Solution", "Proof or case", "Call to action"],
        "template": "不是 X 不行，而是你没有找到适合自己的 Y。"
        if language == "zh"
        else "It is not that X does not work; you have not found the right Y for your situation.",
    }
    prompt_payload = {
        "source_url": source_url,
        "raw_script": raw_script,
        "industry": INDUSTRY_LABELS[industry],
        "language": output_language,
        "requirements": [
            "学习爆款结构，但不要逐字复制原文案",
            "分析黄金开头、痛点、反差、好奇心、利益点、情绪点、信任背书",
            "生成适合数字人口播的原创口播稿",
            "必须先识别 source_video_core，再完整输出 topic、hook、selling_points、structure、template、rewrites",
            "source_video_core 必须包含 core_event、core_conflict、key_entities、causal_chain、business_implication、audience_takeaway",
            "改写必须围绕原视频主线展开，不能只抓标题、表层热点或单一真假辟谣角度发挥",
            "版本A的反差要来自原视频内部矛盾，例如表面事件和背后供应链/技术/商业风险的反差",
            "版本B的用户痛点要绑定原视频主线，说明只看标题会错过哪些真实风险或机会",
            "版本C必须保留原视频里的商业/行业判断，例如供应链、关键材料、技术量产、地缘政治或产业链机会",
            "所有最终文案只能使用 raw_script、metadata、analysis 和 source_video_core 已有信息，不能新增没有来源支撑的具体事实、实体、供应链环节或投资判断",
            "如果 raw_script、metadata、analysis 或 source_video_core 已经出现“供应链、产业链、风险、机会、技术依赖、关键材料、产能、成本压力”等主题，最终 rewrites 必须保留这些已知主题",
            "不要因为保守而退回只讲招股书缺失、官方文件空白、信息真假或市场猜测",
            "如果来源没有明确出现，不要写政府合同、私人融资、不锈钢壳、发动机、地面设施等具体环节",
            "没有来源支撑的推测必须保守表达，可以用“可能、值得关注、需要进一步验证、观察角度”，不要写成确定事实",
            "禁止过度确定判断，例如“未来的金矿、一定受益、根本不需要上市、必然影响、确定机会”",
            "禁止箭头链条表达，例如“上市传闻→招股书未披露→市场猜测”，也不要写“差异分析、实质性进展待确认、市场猜测和不确定性、正式文件最靠谱”等报告腔",
            "selling_points 至少 4 条，structure 至少 5 条",
            "rewrites 必须至少 3 条，每条 script 不少于 80 个中文字符，建议 100-180 字",
            "每条 rewrite.script 必须包含开头钩子、问题/反差、信息价值、行动号召",
            "rewrites 之间必须明显差异化：版本A偏悬念揭秘/反常识，版本B偏用户痛点/普通人视角，版本C偏机会提醒/行动建议",
            "只输出 3 条高质量版本即可：版本A热点反差版、版本B用户痛点版、版本C商业机会版",
            "每条文案的开头、结尾、语气不能重复；同一批文案中“下一条继续拆”最多出现 1 次，“先收藏”最多出现 1 次",
            "不要每条都用“关注我”结尾，不要连续多条使用相同 CTA，不要重复“普通人看结果，懂内容的人会先问”这类固定句式",
            "不要重复使用“这类内容好用的地方”“既能承接热点流量，也能展示你的专业判断”“想看我继续拆这个方向”等句式骨架",
            "版本A面向泛用户，用热点反差和观点讨论收尾；版本B面向内容创作者，用痛点和应用建议收尾；版本C面向老板/行业观察者，用产业链机会和后续观察收尾",
            "rewrite.title 只写版本名称；rewrite.script 只能写最终口播成稿，必须是可以直接朗读给观众听的正文",
            "rewrite.script 禁止出现模板说明、分析说明、结构说明、可复用模板、版本解释、括号结构、字段名、JSON 残留",
            "rewrite.script 禁止出现“可复用模板是”“这个版本适合”“建议用户”“（疑问/反常识开头）+”等生成策略说明",
            "不允许只输出标题或一句短句，不允许输出“信息不足无法分析”",
            "如果输入来自短视频分享文案或链接公开信息，仍必须基于已有信息做初步拆解并完整输出结构",
            "不要编造具体数据；未知内容用“可能、可关注、可延伸”等表达",
            "避免侵权表达，不使用疑似原文的连续句子",
            "避免承诺绝对收益、保证效果、夸大医疗或金融效果",
            "输出严格 JSON，不要 markdown，不要解释 JSON 之外的内容",
        ],
        "schema": {
            "topic": "视频核心主题",
            "hook": "黄金开头，前 3 秒吸引点",
            "selling_points": ["痛点", "反差", "好奇心", "利益点", "情绪点", "信任背书"],
            "structure": ["开头钩子：...", "问题放大：...", "解决方案/信息增量：...", "证明/案例：...", "行动号召：..."],
            "template": "可复用模板公式",
            "source_video_core": {
                "core_event": "原视频讨论的核心事件",
                "core_conflict": "原视频里的核心矛盾",
                "key_entities": ["公司", "行业", "供应链", "材料", "国家/地区", "用户群体"],
                "causal_chain": "原视频的关键因果链",
                "business_implication": "原视频给出的商业或行业判断",
                "audience_takeaway": "观众应该带走的真实重点",
            },
            "rewrites": [
                {"title": "版本A：稳健拆解版", "script": "直接对观众说的 100-180 字原创口播成稿，不包含模板说明"},
                {"title": "版本B：强钩子口播版", "script": "直接对观众说的 100-180 字原创口播成稿，不包含结构说明"},
                {"title": "版本C：转化引导版", "script": "直接对观众说的 100-180 字原创口播成稿，不包含版本解释"},
            ],
        },
    }

    data = await LLMProvider().generate_json(
        system=(
            "你是短视频爆款文案拆解专家和数字人口播编导。"
            "你的任务是提炼结构和创作方法，并生成原创改写稿。"
            f"目标输出语言是{output_language}。除字段名外，所有内容必须使用{output_language}。只输出合法 JSON。"
        ),
        payload=prompt_payload,
    )

    result = validate_viral_analysis_payload(
        {
            "topic": data.get("topic") or fallback_text["topic"],
            "hook": data.get("hook") or fallback_text["hook"],
            "selling_points": data.get("selling_points") or fallback_text["selling_points"],
            "structure": data.get("structure") or fallback_text["structure"],
            "template": data.get("template") or data.get("template_formula") or fallback_text["template"],
            "raw_script": raw_script,
            "source_video_core": data.get("source_video_core") or data.get("sourceVideoCore"),
            "rewrites": data.get("rewrites") or data.get("rewrite_versions") or data.get("rewriteVersions") or data.get("scripts"),
        },
        language=language,
    )

    try:
        supabase.table("viral_analyses").insert(
            {
                "user_id": user_id,
                "source_url": source_url,
                "raw_script": raw_script,
                "industry": industry,
                "language": language,
                "topic": result["topic"],
                "hook": result["hook"],
                "selling_points": result["selling_points"],
                "structure": result["structure"],
                "template_text": result["template"],
                "rewrites": result["rewrites"],
            }
        ).execute()
    except APIError:
        pass

    try:
        supabase.table("usage_logs").insert(
            {
                "user_id": user_id,
                "action": "viral_analyze",
                "quantity": 1,
                "period_start": current_period_start(),
            }
        ).execute()
    except APIError:
        pass

    return {**result, "quota": {**quota, "used": quota["used"] + 1}}
