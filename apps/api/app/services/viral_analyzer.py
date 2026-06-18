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
}

PLAN_LIMITS: dict[str, int | None] = {
    "free": 5,
    "plus": 100,
    "pro": 300,
    "business": None,
}


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


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


def _active_viral_extra_quota(supabase: Client, *, user_id: str) -> dict[str, Any]:
    try:
        result = (
            supabase.table("viral_quota_overrides")
            .select("extra_monthly_limit,expires_at")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except APIError:
        return {"extra_limit": 0, "extra_expires_at": None}

    if not result.data:
        return {"extra_limit": 0, "extra_expires_at": None}

    override = result.data[0]
    expires_at = _parse_datetime(override.get("expires_at"))
    if expires_at is not None and expires_at <= datetime.now(UTC):
        return {"extra_limit": 0, "extra_expires_at": override.get("expires_at")}

    try:
        extra_limit = int(override.get("extra_monthly_limit") or 0)
    except (TypeError, ValueError):
        extra_limit = 0
    return {"extra_limit": max(extra_limit, 0), "extra_expires_at": override.get("expires_at")}


def _assert_viral_quota(supabase: Client, *, user_id: str, email: str) -> dict[str, Any]:
    profile = ensure_profile(supabase, user_id=user_id, email=email)
    plan = profile.get("plan") or "free"
    base_limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    extra_quota = {"extra_limit": 0, "extra_expires_at": None}
    limit = base_limit
    if base_limit is not None:
        extra_quota = _active_viral_extra_quota(supabase, user_id=user_id)
        limit = base_limit + extra_quota["extra_limit"]
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
                "effective_monthly_limit": limit,
                "base_limit": base_limit,
                **extra_quota,
            },
        )
    return {
        "plan": plan,
        "used": used,
        "monthly_limit": limit,
        "effective_monthly_limit": limit,
        "base_limit": base_limit,
        **extra_quota,
    }


def _list_of_strings(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or fallback
    return fallback


def _rewrites(value: Any, fallback_topic: str) -> list[dict[str, str]]:
    default = [
        {"title": "保守版", "script": f"今天用一个更清晰的角度，重新聊聊{fallback_topic}。先看问题，再看方法，最后给你一个可以直接执行的建议。"},
        {"title": "强转化版", "script": f"如果你也在为{fallback_topic}纠结，先别急着做决定。真正拉开差距的不是投入更多，而是找到更适合你的方法。"},
        {"title": "短视频口播版", "script": f"很多人做不好{fallback_topic}，不是能力不行，而是开头、节奏和转化点都没设计好。"},
    ]
    if not isinstance(value, list):
        return default
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        script = str(item.get("script") or "").strip()
        if title and script:
            normalized.append({"title": title, "script": script})
    if len(normalized) < 3:
        existing_titles = {item["title"] for item in normalized}
        normalized.extend([item for item in default if item["title"] not in existing_titles])
    return normalized[:3]


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
    prompt_payload = {
        "source_url": source_url,
        "raw_script": raw_script,
        "industry": INDUSTRY_LABELS[industry],
        "language": output_language,
        "requirements": [
            "学习爆款结构，但不要逐字复制原文案",
            "分析黄金开头、痛点、反差、好奇心、利益点、情绪点、信任背书",
            "生成适合数字人口播的原创口播稿",
            "避免侵权表达，不使用疑似原文的连续句子",
            "避免承诺绝对收益、保证效果、夸大医疗或金融效果",
            "输出严格 JSON，不要 markdown，不要解释 JSON 之外的内容",
        ],
        "schema": {
            "topic": "视频核心主题",
            "hook": "黄金开头，前 3 秒吸引点",
            "selling_points": ["痛点", "反差", "好奇心", "利益点", "情绪点", "信任背书"],
            "structure": ["开头钩子", "问题放大", "解决方案", "证明/案例", "行动号召"],
            "template": "可复用模板公式",
            "rewrites": [
                {"title": "保守版", "script": "原创口播稿"},
                {"title": "强转化版", "script": "原创口播稿"},
                {"title": "短视频口播版", "script": "原创口播稿"},
            ],
        },
    }

    data = await LLMProvider().generate_json(
        system=(
            "你是短视频爆款文案拆解专家和数字人口播编导。"
            "你的任务是提炼结构和创作方法，并生成原创改写稿。"
            f"除字段名外，内容使用{output_language}。只输出合法 JSON。"
        ),
        payload=prompt_payload,
    )

    topic = str(data.get("topic") or "短视频内容拆解").strip()
    result = {
        "topic": topic,
        "hook": str(data.get("hook") or "用强问题或反差在前 3 秒抓住注意力。").strip(),
        "selling_points": _list_of_strings(
            data.get("selling_points"),
            ["痛点明确", "反差制造注意力", "好奇心推动完播", "利益点清晰", "情绪共鸣", "信任背书"],
        ),
        "structure": _list_of_strings(
            data.get("structure"),
            ["开头钩子", "问题放大", "解决方案", "证明/案例", "行动号召"],
        ),
        "template": str(data.get("template") or "不是 X 不行，而是你没有找到适合自己的 Y。").strip(),
        "rewrites": _rewrites(data.get("rewrites"), topic),
    }

    project_id = ""
    try:
        insert_result = supabase.table("viral_analyses").insert(
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
        if insert_result.data and isinstance(insert_result.data, list):
            project_id = str(insert_result.data[0].get("id") or "")
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

    return {**result, "project_id": project_id, "quota": {**quota, "used": quota["used"] + 1}}
