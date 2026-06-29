from __future__ import annotations

from datetime import UTC, datetime
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


def _expand_rewrite_script(script: str, *, topic: str, hook: str, template: str, language: str, variant: str) -> str:
    text = script.strip()
    if language != "zh":
        if len(text.split()) >= 70:
            return text
        return (
            f"{text} Start with the key contrast around {topic}, explain why the audience should care, "
            f"turn the idea into a practical takeaway, and close with a clear next step. "
            f"Use this reusable structure: {template}."
        ).strip()
    if _cjk_len(text) >= MIN_REWRITE_CJK_CHARS:
        return text
    opening = text or hook or f"很多人看到{topic}，第一反应只是跟热点。"
    expansion = (
        f"{opening} 但真正值得拆的不是表面的热闹，而是它先用一个反差把注意力抓住，"
        f"再把用户关心的问题讲清楚。围绕{topic}，你可以先抛出疑问，再补充关键线索，"
        f"接着给出可延伸的判断，最后提醒观众关注后续变化或结合自己的场景行动。"
        f"{variant}可以复用的结构是：{template}"
    )
    return expansion.strip()


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
            f"很多人看到{topic}，只会复述新闻，但爆款不会停在信息表面。它会先制造一个疑问：为什么这件事值得现在关注？再把问题、线索和影响讲清楚，最后提醒观众把这个结构用到自己的内容里。",
        ),
        (
            "版本C：转化引导版",
            f"如果你也想做{topic}这类内容，别急着照搬标题。先用一句话抓住反差，再放大观众关心的问题，接着给出一个有价值的判断，最后用一句行动号召收尾，让用户愿意评论、收藏或继续追更。",
        ),
    ]
    return [{"title": title, "script": _expand_rewrite_script(script, topic=topic, hook=hook, template=template, language=language, variant=title)} for title, script in base]


def _rewrites(value: Any, fallback_topic: str, language: str) -> list[dict[str, str]]:
    default = _default_rewrites(fallback_topic, "先用一个反差问题抓住注意力。", "开头钩子 + 问题放大 + 信息价值 + 行动号召", language)
    if isinstance(value, str):
        value = [{"title": "基础版" if language == "zh" else "Base version", "script": value}]
    if not isinstance(value, list):
        return default
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
    repaired: list[dict[str, str]] = []
    for index, item in enumerate(normalized[:MIN_REWRITE_COUNT]):
        title = item["title"] or default[index]["title"]
        script = _expand_rewrite_script(
            item["script"],
            topic=fallback_topic,
            hook="先用一个反差问题抓住注意力。",
            template="开头钩子 + 问题放大 + 信息价值 + 行动号召",
            language=language,
            variant=title,
        )
        repaired.append({"title": title, "script": script})
    return repaired


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
    normalized_rewrites = _rewrites(rewrites_value, topic, language)
    normalized_rewrites = [
        {
            "title": item["title"],
            "script": _expand_rewrite_script(item["script"], topic=topic, hook=hook, template=template, language=language, variant=item["title"]),
        }
        for item in normalized_rewrites
    ]
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
                {"title": "版本A：稳健拆解版", "script": "100-180 字原创口播稿，包含钩子、问题/反差、信息价值、行动号召"},
                {"title": "版本B：强钩子口播版", "script": "100-180 字原创口播稿，包含钩子、问题/反差、信息价值、行动号召"},
                {"title": "版本C：转化引导版", "script": "100-180 字原创口播稿，包含钩子、问题/反差、信息价值、行动号召"},
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
