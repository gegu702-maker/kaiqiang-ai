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
    r"先收藏[。！!]*"
)
SCRIPT_PUNCT_RE = re.compile(r"[\s，。！？、；：,.!?;:\"'“”‘’（）()\[\]【】《》<>-]+")

CTA_POOL = [
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
STYLE_KEYS = [
    "suspense",
    "pain_point",
    "opportunity",
    "boss_view",
    "knowledge",
    "story",
    "live_stream",
    "minimal",
    "conversion",
]


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


def _cjk_len(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


def sanitize_rewrite_script(script: str) -> str:
    text = str(script or "").strip()
    text = SCRIPT_PREFIX_RE.sub("", text)
    text = TEMPLATE_BLOCK_RE.sub("", text)
    text = BRACKET_TEMPLATE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ：:，,。；;")


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
    return STYLE_KEYS[index % len(STYLE_KEYS)]


def _cta_for_index(index: int) -> str:
    return CTA_POOL[index % len(CTA_POOL)]


def _trim_common_cta(script: str) -> str:
    text = COMMON_CTA_RE.sub("", str(script or ""))
    for cta in CTA_POOL:
        text = text.replace(cta, "")
        text = text.replace(cta.rstrip("。！？!"), "")
    return re.sub(r"\s+", " ", text).strip(" ，。！？；;")


def _script_with_unique_cta(script: str, index: int) -> str:
    text = _trim_common_cta(script)
    cta = _cta_for_index(index)
    if cta in text:
        return text
    return f"{text}。{cta}".strip(" 。")


def _compose_diverse_script(*, topic: str, hook: str, template: str, language: str, style: str, seed: str, index: int) -> str:
    if language != "zh":
        base = (
            f"{seed or hook or topic} Start from a clear contrast, explain why {topic} matters, "
            "turn the point into one practical takeaway, and close with a viewer action that differs from the other versions."
        )
        return base.strip()

    topic_text = topic or "这个热点"
    hook_text = sanitize_rewrite_script(seed) or hook or f"{topic_text}真正值得关注的地方，可能不是你第一眼看到的热闹。"
    lines = {
        "suspense": (
            f"你有没有发现，{topic_text}最值得拆的不是热搜本身，而是它背后那条反常识线索。"
            f"{hook_text} 先把悬念抛出来，再告诉观众为什么这件事突然值得关注，最后把可能影响讲清楚。"
        ),
        "pain_point": (
            f"如果你经常看热点，却不知道怎么把它变成自己的内容，{topic_text}就是一个很好的样本。"
            "别只复述发生了什么，要先说普通人最容易忽略的痛点，再给出一个能马上拿去用的判断。"
        ),
        "opportunity": (
            f"{topic_text}真正有价值的地方，是它可能释放出的机会信号。"
            "表面看是一个新闻点，往深一层看，是用户注意力、产业变化和内容选题之间的连接。"
        ),
        "boss_view": (
            f"站在老板或创业者视角看，{topic_text}不只是一个热点，而是一次判断趋势的练习。"
            "你要看的不是谁赢谁输，而是谁在供应链、流量入口和用户认知里拿到了新位置。"
        ),
        "knowledge": (
            f"把{topic_text}拆成一个知识点，其实很简单：先讲背景，再讲反差，最后讲它为什么会影响普通人的判断。"
            "这样观众听到的不只是消息，而是一套以后还能复用的分析方法。"
        ),
        "story": (
            f"这条内容可以讲成一个转折故事：一开始大家只看到{topic_text}的表面热闹，"
            "但越往后看，越会发现真正推动讨论的是隐藏在细节里的变化。"
        ),
        "live_stream": (
            f"家人们先别急着刷过去，{topic_text}这件事表面像新闻，实际很适合拆成一个能互动的话题。"
            "我们先看矛盾点，再看谁会受到影响，最后看你能不能把它改成自己的选题。"
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
    value = "这类内容好用的地方，是既能承接热点流量，也能把你的专业判断展示出来。"
    return _script_with_unique_cta(f"{body}{value}", index)


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


def _expand_rewrite_script(script: str, *, topic: str, hook: str, template: str, language: str, variant: str, index: int = 0) -> str:
    text = sanitize_rewrite_script(script)
    style = _style_for_index(index, variant)
    if language != "zh":
        if len(text.split()) >= 70 and not is_script_polluted(text):
            return text
        return _compose_diverse_script(topic=topic, hook=hook, template=template, language=language, style=style, seed=text, index=index)
    if _cjk_len(text) >= MIN_REWRITE_CJK_CHARS and not is_script_polluted(text):
        return _script_with_unique_cta(text, index)
    return _compose_diverse_script(topic=topic, hook=hook, template=template, language=language, style=style, seed=text, index=index)


def dedupe_and_diversify_rewrites(
    rewrites: list[dict[str, str]],
    *,
    topic: str,
    hook: str,
    template: str,
    language: str,
    limit: int = 9,
) -> list[dict[str, str]]:
    diversified: list[dict[str, str]] = []
    for index, item in enumerate(rewrites):
        title = str(item.get("title") or (f"版本{index + 1}" if language == "zh" else f"Version {index + 1}")).strip()
        script = _expand_rewrite_script(
            str(item.get("script") or ""),
            topic=topic,
            hook=hook,
            template=template,
            language=language,
            variant=title,
            index=index,
        )
        if is_script_polluted(script) or _cjk_len(script) < MIN_REWRITE_CJK_CHARS:
            script = _compose_diverse_script(
                topic=topic,
                hook=hook,
                template=template,
                language=language,
                style=_style_for_index(index, title),
                seed="",
                index=index,
            )
        if any(rewrite_similarity(script, previous["script"]) > 0.65 for previous in diversified):
            script = _compose_diverse_script(
                topic=topic,
                hook=hook,
                template=template,
                language=language,
                style=_style_for_index(index + 3, title),
                seed="",
                index=index,
            )
        diversified.append({"title": title, "script": script})
        if len(diversified) >= limit:
            break
    return diversified


def _default_rewrites(topic: str, hook: str, template: str, language: str) -> list[dict[str, str]]:
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
            f"{hook} 这条内容真正值得学习的，不只是{topic}本身，而是它把一个热点讲成了观众愿意继续听的问题。开头先抛出反差，中间补充关键线索，再给出可延伸的判断，最后引导大家关注后续变化。",
        ),
        (
            "版本B：强钩子口播版",
            f"很多人看到{topic}，只会复述新闻，但真正能吸引人的内容不会停在表面。它会先制造一个疑问：为什么这件事值得现在关注？再把问题、线索和影响讲清楚，最后提醒观众继续关注后续变化。",
        ),
        (
            "版本C：转化引导版",
            f"如果你也想做{topic}这类内容，别急着照搬标题。先用一句话抓住反差，再放大观众关心的问题，接着给出一个有价值的判断，最后用一句行动号召收尾，让用户愿意评论、收藏或继续追更。",
        ),
    ]
    return [
        {"title": title, "script": _expand_rewrite_script(script, topic=topic, hook=hook, template=template, language=language, variant=title, index=index)}
        for index, (title, script) in enumerate(base)
    ]


def _rewrites(value: Any, fallback_topic: str, language: str, *, hook: str = "", template: str = "") -> list[dict[str, str]]:
    fallback_hook = hook or "先用一个反差问题抓住注意力。"
    fallback_template = template or "开头钩子 + 问题放大 + 信息价值 + 行动号召"
    default = _default_rewrites(fallback_topic, fallback_hook, fallback_template, language)
    if isinstance(value, str):
        value = [{"title": "基础版" if language == "zh" else "Base version", "script": value}]
    if not isinstance(value, list):
        return dedupe_and_diversify_rewrites(
            default,
            topic=fallback_topic,
            hook=fallback_hook,
            template=fallback_template,
            language=language,
            limit=MIN_REWRITE_COUNT,
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
        limit=MIN_REWRITE_COUNT,
    )


def validate_viral_analysis_payload(payload: dict[str, Any], *, language: str) -> dict[str, Any]:
    topic = str(payload.get("topic") or ("短视频内容拆解" if language == "zh" else "Short video content analysis")).strip()
    hook = str(payload.get("hook") or ("先用一个反差问题抓住注意力。" if language == "zh" else "Start with a contrast question.")).strip()
    template = str(
        payload.get("template")
        or payload.get("template_formula")
        or ("开头钩子 + 问题放大 + 信息价值 + 行动号召" if language == "zh" else "Hook + Problem + Value + CTA")
    ).strip()
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
    normalized_rewrites = _rewrites(rewrites_value, topic, language, hook=hook, template=template)
    return {
        "topic": topic,
        "hook": hook,
        "selling_points": selling_points,
        "structure": structure,
        "template": template,
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
            "必须完整输出 topic、hook、selling_points、structure、template、rewrites",
            "selling_points 至少 4 条，structure 至少 5 条",
            "rewrites 必须至少 3 条，每条 script 不少于 80 个中文字符，建议 100-180 字",
            "每条 rewrite.script 必须包含开头钩子、问题/反差、信息价值、行动号召",
            "rewrites 之间必须明显差异化：版本A偏悬念揭秘/反常识，版本B偏用户痛点/普通人视角，版本C偏机会提醒/行动建议",
            "如果输出更多版本，可使用直播口吻、老板视角、知识分享、故事版、极简强钩子、成交转化等不同角度",
            "每条文案的开头、结尾、语气不能重复；同一批文案中“下一条继续拆”最多出现 1 次，“先收藏”最多出现 1 次",
            "不要每条都用“关注我”结尾，不要连续多条使用相同 CTA，不要重复“普通人看结果，懂内容的人会先问”这类固定句式",
            "至少一条像新闻解读，一条像朋友提醒，一条像知识科普；有更多版本时可加入老板/创业者视角或直播间口吻",
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
