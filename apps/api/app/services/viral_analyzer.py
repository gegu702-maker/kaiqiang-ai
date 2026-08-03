from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from difflib import SequenceMatcher
import logging
import math
import random
import re
import time
from typing import Any

from fastapi import HTTPException
from postgrest.exceptions import APIError
from supabase import Client

from app.services.billing import current_period_start, ensure_profile
from app.services.llm_provider import LLMProvider, LLMProviderError
from app.services.viral_diagnostics import current_request_id
from app.services.viral_fact_fidelity import (
    build_source_fact_ledger,
    map_source_fact_coverage,
    unsupported_hard_facts,
)
from app.services.viral_length import (
    calculate_public_metadata_target,
    calculate_rewrite_length_target,
    normalize_length_mode,
)

logger = logging.getLogger(__name__)

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
    "这个版本适合",
    "分析如下",
    "+（",
    "+【",
    "（开头",
    "（痛点",
    "（行动号召",
    "【热点事件】",
)
SCRIPT_PREFIX_RE = re.compile(r"^\s*(?:script|文案|口播文案|正文|版本[A-ZＡ-Ｚ]?)\s*[:：]\s*", re.IGNORECASE)
TEMPLATE_META_SENTENCE_RE = re.compile(
    r"(?:^|(?<=[。！？!?]))\s*"
    r"(?:可复用模板是|可套用模板是|该版本的模板|这个版本适合|"
    r"建议用户\s*[:：]|分析\s*[:：]|结构\s*[:：]|可套用模板\s*[:：]|可复用模板\s*[:：])"
    r"[^。！？!?]*(?:[。！？!?]|$)"
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
MAX_REWRITE_SUPPLEMENT_ROUNDS = 2
# Real Preview requests returned roughly 22%–40% of the requested Chinese
# characters in low-yield rounds. Use the conservative end of that evidence
# instead of assuming that the model will follow an exact character count.
REWRITE_HISTORICAL_YIELD_FLOOR = 0.25
REWRITE_MIN_OBSERVED_YIELD = 0.10
REWRITE_MAX_PLANNING_YIELD = 0.50
REWRITE_SECOND_ROUND_MULTIPLIER = 1.25
MAX_REQUESTED_ADDITIONAL_CJK_CHARS = 1800
MAX_SUPPLEMENT_RESPONSE_TOKENS = 8000
MAX_SOURCE_CONSTRAINED_LLM_CALLS = 9
PRIMARY_CONVERGENCE_MAX_CALLS = 2
SCAFFOLD_POLISH_RESERVED_CALLS = 1
MAX_LENGTH_ONLY_RESCUE_GAP = 12
MIN_SOURCE_FACT_COVERAGE_RATE = 0.35
MAX_VARIANT_SIMILARITY = 0.75
SOURCE_INITIAL_CONCURRENCY = 2
SOURCE_INITIAL_MAX_NETWORK_RETRIES = 1
SOURCE_INITIAL_MAX_EXHAUSTION_REGENERATIONS = 1
SOURCE_RETRY_BASE_DELAY_SECONDS = 0.4
SOURCE_RETRY_JITTER_SECONDS = 0.2


class _LLMCallBudgetExceeded(Exception):
    pass


class _LLMCallBudget:
    def __init__(self, maximum_calls: int) -> None:
        self.maximum_calls = maximum_calls
        self.used_calls = 0
        self._lock = asyncio.Lock()

    async def reserve(self) -> int:
        async with self._lock:
            if self.used_calls >= self.maximum_calls:
                raise _LLMCallBudgetExceeded
            self.used_calls += 1
            return self.used_calls


def _retryable_initial_provider_error(error: LLMProviderError) -> bool:
    if error.code in {
        "llm_timeout",
        "llm_network_error",
        "llm_rate_limited",
        "llm_upstream_timeout",
    }:
        return True
    return (
        error.code == "llm_http_error"
        and error.retryable
        and error.http_status is not None
        and error.http_status >= 500
    )
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
    ("先别急着模仿表面内容", "别先忙着照搬原视频"),
    ("结构", "节奏"),
    ("你觉得的重点", "你觉得重点"),
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


def _cjk_len(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


def _planned_supplement_chars(
    *,
    current_chars: int,
    desired_final_chars: int,
    supplement_round: int,
    previous_requested_chars: int | None = None,
    previous_returned_chars: int | None = None,
) -> tuple[int, float]:
    desired_additional_chars = max(1, desired_final_chars - current_chars)
    planning_yield = REWRITE_HISTORICAL_YIELD_FLOOR
    multiplier = 1.0
    if supplement_round > 1 and previous_requested_chars:
        observed_yield = max(0.0, (previous_returned_chars or 0) / previous_requested_chars)
        planning_yield = min(
            REWRITE_MAX_PLANNING_YIELD,
            max(REWRITE_MIN_OBSERVED_YIELD, observed_yield),
        )
        multiplier = REWRITE_SECOND_ROUND_MULTIPLIER
    requested_chars = math.ceil(desired_additional_chars / planning_yield * multiplier)
    return min(MAX_REQUESTED_ADDITIONAL_CJK_CHARS, requested_chars), planning_yield


def _trim_to_sentence_boundary(value: str, *, minimum_chars: int, maximum_chars: int) -> str:
    text = str(value or "").strip()
    if _cjk_len(text) <= maximum_chars:
        return text

    candidates: list[str] = []
    for match in re.finditer(r"[。！？!?](?:[”’\"])?", text):
        candidate = text[: match.end()].strip()
        candidate_chars = _cjk_len(candidate)
        if minimum_chars <= candidate_chars <= maximum_chars:
            candidates.append(candidate)
    return candidates[-1] if candidates else text


def _repeated_sentence_spans(value: str) -> list[str]:
    seen: set[str] = set()
    repeated: list[str] = []
    for sentence in re.split(r"(?<=[。！？!?])", str(value or "")):
        normalized = SCRIPT_PUNCT_RE.sub("", sentence)
        if len(normalized) < 12:
            continue
        if normalized in seen and normalized not in repeated:
            repeated.append(normalized)
        seen.add(normalized)
    return repeated


def _source_backed_scaffold(
    *,
    source_fact_ledger: dict[str, Any],
    index: int,
    minimum_chars: int,
    target_center_chars: int,
    maximum_chars: int,
) -> str:
    """Build one bounded primary fallback from unique source sentences only."""
    _ = index
    facts = [
        {**fact, "_source_order": order}
        for order, fact in enumerate(source_fact_ledger.get("facts") or [])
        if isinstance(fact, dict) and str(fact.get("evidence") or "").strip()
    ]
    selected: list[str] = []
    seen: set[str] = set()
    current_chars = 0
    for fact in facts:
        evidence = re.sub(r"[\r\n]+", "，", str(fact.get("evidence") or ""))
        evidence = re.sub(r"，{2,}", "，", evidence).strip(" ，")
        evidence = _with_sentence_end(evidence)
        normalized = _normalize_for_similarity(evidence)
        if not normalized or normalized in seen:
            continue
        candidate_chars = current_chars + _cjk_len(evidence)
        if candidate_chars > maximum_chars:
            continue
        seen.add(normalized)
        selected.append(evidence)
        current_chars += _cjk_len(evidence)
        if current_chars >= target_center_chars:
            break

    if current_chars < minimum_chars:
        for fact in facts:
            evidence = re.sub(r"[\r\n]+", "，", str(fact.get("evidence") or ""))
            evidence = re.sub(r"，{2,}", "，", evidence).strip(" ，")
            evidence = _with_sentence_end(evidence)
            normalized = _normalize_for_similarity(evidence)
            if not normalized or normalized in seen:
                continue
            if current_chars + _cjk_len(evidence) > maximum_chars:
                continue
            seen.add(normalized)
            selected.append(evidence)
            current_chars += _cjk_len(evidence)
            if current_chars >= minimum_chars:
                break
    return _natural_paragraphs("".join(selected).strip())


def _natural_paragraphs(script: str, *, target_paragraph_chars: int = 220) -> str:
    """Normalize ASR newlines and group complete sentences into readable paragraphs."""
    normalized = re.sub(r"\s+", " ", str(script or "")).strip()
    if not normalized:
        return ""
    sentences = [item.strip() for item in re.split(r"(?<=[。！？!?])", normalized) if item.strip()]
    if len(sentences) <= 1:
        return normalized
    paragraphs: list[str] = []
    current: list[str] = []
    current_chars = 0
    for sentence in sentences:
        current.append(sentence)
        current_chars += _cjk_len(sentence)
        if current_chars >= target_paragraph_chars:
            paragraphs.append("".join(current))
            current = []
            current_chars = 0
    if current:
        paragraphs.append("".join(current))
    return "\n\n".join(paragraphs)


def _candidate_quality_snapshot(
    *,
    index: int,
    rewrite: dict[str, Any],
    raw_script: str,
    source_fact_ledger: dict[str, Any],
    minimum_chars: int,
    maximum_chars: int,
    minimum_fact_coverage_count: int,
) -> dict[str, Any]:
    claimed_ids = list(dict.fromkeys(rewrite.get("used_source_fact_ids") or []))
    script = str(rewrite.get("script") or "")
    mapping = map_source_fact_coverage(
        source_fact_ledger,
        script,
        claimed_fact_ids=claimed_ids,
    )
    actual_chars = _cjk_len(script)
    directly_supported_ids = list(mapping["directly_supported_fact_ids"])
    hard_violations = unsupported_hard_facts(raw_script, script)
    repeated = _repeated_sentence_spans(script)
    if actual_chars < minimum_chars:
        length_gap = minimum_chars - actual_chars
        length_gap_direction = "below_minimum"
    elif actual_chars > maximum_chars:
        length_gap = actual_chars - maximum_chars
        length_gap_direction = "above_maximum"
    else:
        length_gap = 0
        length_gap_direction = "in_range"
    coverage = {
        "index": index,
        "model_claimed_fact_ids": claimed_ids,
        "directly_supported_fact_ids": directly_supported_ids,
        "used_source_fact_ids": directly_supported_ids,
        "uncertain_fact_ids": mapping["uncertain_fact_ids"],
        "unsupported_spans": mapping["unsupported_spans"],
        "unused_source_fact_ids": [
            fact_id
            for fact_id in source_fact_ledger["fact_ids"]
            if fact_id not in directly_supported_ids
        ],
        "used_count": len(directly_supported_ids),
        "total_count": source_fact_ledger["fact_count"],
        "coverage_rate": (
            round(len(directly_supported_ids) / source_fact_ledger["fact_count"], 4)
            if source_fact_ledger["fact_count"]
            else 0.0
        ),
    }
    reasons: list[str] = []
    if not minimum_chars <= actual_chars <= maximum_chars:
        reasons.append("length")
    if hard_violations:
        reasons.append("hard_fact")
    if mapping["unsupported_spans"]:
        reasons.append("unsupported")
    if len(directly_supported_ids) < minimum_fact_coverage_count:
        reasons.append("source_fact_coverage")
    if not script.rstrip().endswith(tuple("。！？!?")):
        reasons.append("incomplete_ending")
    if repeated:
        reasons.append("internal_repetition")
    return {
        "index": index,
        "rewrite": rewrite,
        "actual_chars": actual_chars,
        "length_gap": length_gap,
        "length_gap_direction": length_gap_direction,
        "coverage": coverage,
        "hard_violations": hard_violations,
        "repeated_spans": repeated,
        "reasons": reasons,
        "exact_failure_reasons": list(reasons),
        "incomplete_ending": "incomplete_ending" in reasons,
        "similarity_failure": False,
        "provenance": str(rewrite.get("provenance") or "independent_initial"),
        "valid": not reasons,
    }


def _candidate_diagnostic_record(
    snapshot: dict[str, Any],
    *,
    similarity_failure: bool | None = None,
) -> dict[str, Any]:
    similarity_failed = (
        bool(snapshot.get("similarity_failure"))
        if similarity_failure is None
        else similarity_failure
    )
    reasons = list(snapshot.get("exact_failure_reasons") or snapshot.get("reasons") or [])
    if similarity_failed and "similarity" not in reasons:
        reasons.append("similarity")
    coverage = snapshot.get("coverage") or {}
    return {
        "index": int(snapshot["index"]),
        "actual_chars": int(snapshot["actual_chars"]),
        "length_gap": int(snapshot.get("length_gap") or 0),
        "length_gap_direction": str(snapshot.get("length_gap_direction") or "in_range"),
        "hard_violations": list(snapshot.get("hard_violations") or []),
        "unsupported_spans": list(coverage.get("unsupported_spans") or []),
        "fact_coverage": {
            "used_count": int(coverage.get("used_count") or 0),
            "total_count": int(coverage.get("total_count") or 0),
            "coverage_rate": float(coverage.get("coverage_rate") or 0.0),
        },
        "incomplete_ending": bool(snapshot.get("incomplete_ending")),
        "repeated_spans": list(snapshot.get("repeated_spans") or []),
        "similarity_failure": similarity_failed,
        "exact_failure_reasons": reasons,
        "provenance": str(snapshot.get("provenance") or "independent_initial"),
        "valid": not reasons,
    }


def _neutral_micro_gap_closing(*, industry: str, raw_script: str) -> str:
    if industry == "personal_brand":
        return "先照顾好自己的感受。"
    if any(marker in raw_script for marker in ("资本市场", "回购", "ETF", "中报", "外资")):
        return "相关信息仍需持续核对。"
    return "以上就是这次的梳理。"


def _is_length_only_micro_gap_rescue_eligible(
    snapshot: dict[str, Any],
    *,
    minimum_fact_coverage_count: int,
    is_primary: bool,
) -> bool:
    return bool(
        not snapshot["valid"]
        and snapshot["provenance"]
        not in {"deterministic_scaffold", "scaffold_polished_by_model"}
        and snapshot["exact_failure_reasons"] == ["length"]
        and snapshot["length_gap_direction"] == "below_minimum"
        and 1 <= snapshot["length_gap"] <= MAX_LENGTH_ONLY_RESCUE_GAP
        and not snapshot["hard_violations"]
        and not snapshot["coverage"]["unsupported_spans"]
        and snapshot["coverage"]["used_count"] >= minimum_fact_coverage_count
        and not snapshot["repeated_spans"]
        and not snapshot["incomplete_ending"]
        and (not snapshot.get("similarity_failure") or is_primary)
    )


def _primary_rank(snapshot: dict[str, Any], *, minimum_chars: int, maximum_chars: int) -> tuple[Any, ...]:
    actual_chars = int(snapshot["actual_chars"])
    if actual_chars < minimum_chars:
        length_distance = minimum_chars - actual_chars
    elif actual_chars > maximum_chars:
        length_distance = actual_chars - maximum_chars
    else:
        length_distance = 0
    return (
        bool(snapshot["hard_violations"]),
        length_distance,
        -int(snapshot["coverage"]["used_count"]),
        "incomplete_ending" in snapshot["reasons"],
        int(snapshot["index"]),
    )


def sanitize_rewrite_script(script: str) -> str:
    text = str(script or "").strip()
    text = SCRIPT_PREFIX_RE.sub("", text)
    text = TEMPLATE_META_SENTENCE_RE.sub("", text)
    text = BRACKET_TEMPLATE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ：:，,；;")


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
    text = re.sub(r"(互动)(你觉得|评论区)", r"\1。\2", text)
    text = re.sub(r"(判断|套用|看)(\s+)(我更想提醒|如果你也在做内容|后面如果)", r"\1。\3", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([。！？!?])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ：:，,；;")


def is_script_polluted(script: str) -> bool:
    text = str(script or "")
    return (
        any(pattern in text for pattern in POLLUTION_PATTERNS)
        or bool(TEMPLATE_META_SENTENCE_RE.search(text))
        or bool(BRACKET_TEMPLATE_RE.search(text))
    )


def _normalize_for_similarity(text: str) -> str:
    return SCRIPT_PUNCT_RE.sub("", str(text or "")).lower()


def rewrite_similarity(left: str, right: str) -> float:
    a = _normalize_for_similarity(left)
    b = _normalize_for_similarity(right)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _variant_fact_subset(
    source_fact_ledger: dict[str, Any],
    index: int,
) -> list[dict[str, Any]]:
    category_priorities = (
        ("机构及表态", "回购及限定条件", "自购与ETF", "风险边界"),
        ("回购及限定条件", "自购与ETF", "中报和产业链", "风险边界"),
        ("中报和产业链", "外资观点", "机构及表态", "风险边界"),
    )
    priorities = category_priorities[index % len(category_priorities)]
    facts = [
        fact
        for fact in (source_fact_ledger.get("facts") or [])
        if isinstance(fact, dict)
    ]
    selected = [fact for fact in facts if str(fact.get("category") or "") in priorities]
    return selected or facts


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


def _compose_diverse_script(*, topic: str, hook: str, template: str, language: str, style: str, seed: str, index: int) -> str:
    strategy = _strategy_for_index(index)
    if language != "zh":
        base = (
            f"{seed or hook or topic} Start from a clear contrast, explain why {topic} matters, "
            "turn the point into one practical takeaway, and close with a viewer action that differs from the other versions."
        )
        return base.strip()

    topic_text = topic or "这个热点"
    hook_text = smooth_spoken_script(_trim_common_cta(seed)) or smooth_spoken_script(hook) or f"{topic_text}有一个容易被忽略的点。"
    lines = {
        "suspense": (
            f"你以为{topic_text}只是一个普通热点？先别急着下结论。"
            f"{_with_sentence_end(hook_text)}大家都在看结果，但我更想看中间没说透的那条线。"
            "把这条线讲清楚，观众才会愿意留下来判断。"
        ),
        "pain_point": (
            f"如果你也在做内容，看到{topic_text}，千万别只把新闻复述一遍。"
            "用户更想听的是：这件事和我有什么关系？我能从里面借到什么选题？"
            "你先把这个问题讲明白，再给一个能马上开拍的角度，内容就会自然很多。"
        ),
        "opportunity": (
            f"如果你是老板或者行业观察者，{topic_text}别只当成一条新闻刷过去。"
            "更值得看的，是谁的需求变了，谁的供给跟不上，哪一段链条可能先出现新机会。"
            "把这些话讲清楚，你的内容就不是蹭热点，而是在帮观众做判断。"
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
    return smooth_spoken_script(_join_sentences(body, strategy["cta"]))


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
    text = smooth_spoken_script(script)
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
        )
        signature = extract_script_signature(script)
        if (
            is_script_polluted(script)
            or _cjk_len(script) < MIN_REWRITE_CJK_CHARS
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
            )
            signature = extract_script_signature(script)
        diversified.append({"title": title, "script": script})
        seen_signatures.add(signature)
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
            f"{hook} 这条内容别只学{topic}本身，更要学它怎么把热点讲成一个让人愿意听下去的问题。开头先抛反差，中间补一条关键线索，最后给出你的判断，观众才会觉得这不是在复述新闻。",
        ),
        (
            "版本B：强钩子口播版",
            f"很多人看到{topic}，第一反应就是照着讲一遍，但这样很难留下观众。你可以先问一句：为什么这件事现在值得关注？再把问题、线索和影响讲清楚，结尾给一个能评论的判断。",
        ),
        (
            "版本C：转化引导版",
            f"如果你也想做{topic}这类内容，别急着照搬标题。先用一句话讲出反差，再说清楚观众为什么要关心，接着给一个你的判断，最后把下一步动作说具体，让用户愿意评论或收藏。",
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
        limit=FINAL_REWRITE_LIMIT,
    )


def validate_viral_analysis_payload(payload: dict[str, Any], *, language: str) -> dict[str, Any]:
    topic = str(payload.get("topic") or ("短视频内容拆解" if language == "zh" else "Short video content analysis")).strip()
    hook = str(payload.get("hook") or ("先用一个反差问题抓住注意力。" if language == "zh" else "Start with a contrast question.")).strip()
    default_template = (
        "开头钩子 + 问题放大 + 信息价值 + 行动号召"
        if language == "zh"
        else "Hook + Problem + Value + CTA"
    )
    template = str(
        payload.get("template")
        or payload.get("template_formula")
        or default_template
    ).strip()
    template = re.sub(r"(?:…{2,}|\.{3,})", "【按来源事实填写】", template)
    if template.count("【按来源事实填写】") > 3:
        template = default_template
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
        "core_points": _list_of_strings(payload.get("core_points"), selling_points),
        "arguments": _list_of_strings(payload.get("arguments"), structure),
        "cases": _list_of_strings(payload.get("cases"), []),
        "data_points": _list_of_strings(payload.get("data_points"), []),
    }


def _chunk_script(text: str, size: int = 5000) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)] or [""]


async def _build_hierarchical_input(raw_script: str, output_language: str) -> tuple[str, int, int]:
    """Summarize every long-text chunk before final synthesis; never slice away the tail."""
    chunks = _chunk_script(raw_script)
    if len(chunks) == 1:
        return raw_script, 0, 1
    summaries: list[str] = []
    prompt_chars = 0
    for index, chunk in enumerate(chunks):
        payload = {
            "part": index + 1,
            "total_parts": len(chunks),
            "transcript_chunk": chunk,
            "requirements": ["保留该段全部观点、论据、案例、数字与因果关系", "不要泛化，不要补写原文没有的事实"],
            "schema": {"summary": "高密度分段摘要"},
        }
        prompt_chars += len(chunk)
        data = await LLMProvider().generate_json(
            system=f"你是长视频分段信息抽取专家。使用{output_language}，只输出 JSON。",
            payload=payload,
            max_tokens=8000,
            thinking_mode="disabled",
        )
        summaries.append(f"[第{index + 1}/{len(chunks)}段]\n{str(data.get('summary') or chunk).strip()}")
    return "\n\n".join(summaries), prompt_chars, len(chunks)


async def analyze_viral_script(
    supabase: Client,
    *,
    user_id: str,
    email: str,
    source_url: str = "",
    raw_script: str = "",
    industry: str,
    language: str,
    rewrite_length: str = "match_source",
    source_scope: str = "full_content",
    effective_speech_seconds: float | None = None,
    source_fact_sentences: list[dict[str, Any]] | None = None,
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
    if len(raw_script) > 120000:
        raise HTTPException(status_code=400, detail="原始文案超过 120000 字，请分批处理。")
    try:
        requested_length_mode = normalize_length_mode(rewrite_length)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rewrite length.")
    if source_scope not in {"full_content", "public_metadata"}:
        raise HTTPException(status_code=400, detail="Invalid source scope.")

    quota = _assert_viral_quota(supabase, user_id=user_id, email=email)
    output_language = LANGUAGE_LABELS[language]
    analysis_input, prompt_input_chars, summary_chunk_count = await _build_hierarchical_input(raw_script, output_language)
    source_cjk = _cjk_len(raw_script)
    if source_scope == "public_metadata":
        length_target = calculate_public_metadata_target(evidence_cjk=source_cjk)
    else:
        length_target = calculate_rewrite_length_target(
            source_cjk=source_cjk,
            length_mode=requested_length_mode,
            effective_speech_seconds=effective_speech_seconds,
        )
    minimum_chars = length_target.target_min_chars
    target_center_chars = length_target.target_center_chars
    maximum_chars = length_target.target_max_chars
    source_fact_ledger = (
        build_source_fact_ledger(raw_script, source_fact_sentences)
        if source_scope == "full_content"
        else {}
    )
    source_fact_ids = set(source_fact_ledger.get("fact_ids") or [])
    length_guidance = (
        f"动态长度模式为 {length_target.length_mode}；每条严格控制在 "
        f"{minimum_chars}–{maximum_chars} 个中文字符，初稿瞄准区间中部约 "
        f"{target_center_chars} 字。保持原文的信息密度、口播节奏和停顿，不为凑字数重复或虚构"
    )
    if source_scope == "public_metadata":
        length_guidance = (
            f"仅基于公开信息的短版；按当前可验证信息量每条约 "
            f"{minimum_chars}–{maximum_chars} 字，不得声称匹配原视频时长，不得为凑字数补写无来源事实"
        )
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
        "content_input": analysis_input,
        "original_transcript_chars": len(raw_script),
        "source_cjk": source_cjk,
        "effective_speech_seconds": length_target.effective_speech_seconds,
        "source_density": length_target.source_density,
        "length_mode": length_target.length_mode,
        "target_min_chars": minimum_chars,
        "target_center_chars": target_center_chars,
        "target_max_chars": maximum_chars,
        "hierarchical_chunk_count": summary_chunk_count,
        "industry": INDUSTRY_LABELS[industry],
        "language": output_language,
        "source_scope": source_scope,
        "requirements": [
            "学习爆款结构，但不要逐字复制原文案",
            "分析黄金开头、痛点、反差、好奇心、利益点、情绪点、信任背书",
            "生成适合数字人口播的原创口播稿",
            "必须完整输出 topic、hook、selling_points、structure、template、core_points、arguments、cases、data_points、rewrites",
            "观点、论据、案例和数据必须能在输入内容中找到依据，不得只重复标题",
            "保持原转写真实信息密度和口播节奏；大量停顿、短句和情绪递进属于内容风格，不得按其他行业语速强行扩写",
            "selling_points 至少 4 条，structure 至少 5 条",
            f"rewrites 必须至少 3 条；当前长度要求：{length_guidance}",
            "中文长度按实际汉字字符数计算，不按 token、空格或标点凑数",
            "每条 rewrite.script 必须包含开头钩子、问题/反差、信息价值、行动号召",
            "rewrites 之间必须明显差异化：版本A偏热点反差，版本B偏用户痛点/普通人误读，版本C偏信息分析与内容表达机会",
            "只输出 3 条高质量版本即可：版本A热点反差版、版本B用户痛点版、版本C商业机会版",
            "每条文案的开头、结尾、语气不能重复；同一批文案中“下一条继续拆”最多出现 1 次，“先收藏”最多出现 1 次",
            "不要每条都用“关注我”结尾，不要连续多条使用相同 CTA，不要重复“普通人看结果，懂内容的人会先问”这类固定句式",
            "不要重复使用“这类内容好用的地方”“既能承接热点流量，也能展示你的专业判断”“想看我继续拆这个方向”等句式骨架",
            "版本A面向泛用户，用热点反差和观点讨论收尾；版本B解释普通用户容易误读哪些来源信号；版本C只谈信息分析与内容表达角度，不得虚构投资机会或新增行业判断",
            "若原文是财经内容，不得新增原文没有的具体数据，不得使用确定性买入或收益承诺，必须使用中性风险表达",
            "禁止用“举个例子”“比如某公司”虚构公司行为、完成进度、持续周期、涨跌结果或因果结果",
            "禁止新增原文没有的完成比例、持续周数/月数/季度数、ROE、股东名单、ETF份额、连续超预期或目标价调整",
            "一般性解释必须明确写成判断方法、可能性或待核对条件，不能伪装成原视频已经发生的事实",
            "若原文是情感、关系或故事内容，保留慢节奏、短句、停顿和情绪递进，不得强行添加商业结论、投资表达或营销式CTA",
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
            "core_points": ["完整核心观点"],
            "arguments": ["支撑观点的论据与逻辑"],
            "cases": ["原视频提及的案例；没有则为空数组"],
            "data_points": ["原视频提及的数据；没有则为空数组"],
            "rewrites": [
                {"title": "版本A：稳健拆解版", "script": length_guidance},
                {"title": "版本B：强钩子口播版", "script": length_guidance},
                {"title": "版本C：转化引导版", "script": length_guidance},
            ],
        },
    }
    if source_scope == "public_metadata":
        prompt_payload["requirements"].extend(
            [
                "输入仅来自链接公开元数据，不得声称已读取完整视频或执行 ASR",
                "必须明确这是非完整拆解，只覆盖公开标题或描述中可验证的信息",
                f"每条生成约 {minimum_chars}–{maximum_chars} 字的"
                "“仅基于公开信息（非完整拆解）”；不得声称匹配原视频时长",
                "先列出公开标题/描述中可以确认的事实，再说明无法确认的视频观点、论据、案例和数据",
                "给出可执行的内容角度或待验证问题时，必须明确写成建议或可能性，不得包装成原视频事实",
                "结尾明确引导用户上传视频或粘贴原稿以获得完整拆解",
                "公开信息没有明确写出的政策、资金、机构、历史案例、数据、因果关系一律不得补写",
                "cases 与 data_points 必须返回空数组；不得把推测包装成原视频事实",
            ]
        )

    stage_timings: list[dict[str, Any]] = []
    llm_budget = _LLMCallBudget(MAX_SOURCE_CONSTRAINED_LLM_CALLS)
    llm_call_count = 0
    independent_initial_results: list[dict[str, Any]] = []
    all_initial_variants_failed = False
    initial_generation_failures: list[dict[str, Any]] = []
    version_states: list[dict[str, Any]] = []
    active_initial_calls = 0
    maximum_initial_concurrency = 0
    if source_scope == "full_content":
        variant_requirements = (
            "热点反差：只用来源事实呈现“信号不等于结论”的反差，不创造新闻、案例或结果",
            "用户痛点：只解释普通用户容易误读哪些来源信号，以及原文给出的核对方法",
            "信息分析与内容表达：说明如何组织原文中的多类信号，不虚构投资机会或新增行业判断",
        )
        multi_variant_requirement_markers = (
            "必须完整输出 topic",
            "rewrites 必须至少",
            "rewrites 之间",
            "只输出 3 条",
            "同一批文案",
            "不要每条都用",
            "版本A面向",
        )
        independent_base_requirements = [
            requirement
            for requirement in prompt_payload["requirements"]
            if not any(marker in requirement for marker in multi_variant_requirement_markers)
        ]
        initial_semaphore = asyncio.Semaphore(SOURCE_INITIAL_CONCURRENCY)
        concurrency_lock = asyncio.Lock()
        version_states = [
            {
                "index": index,
                "state": "pending",
                "attempts": [],
                "has_valid_response": False,
            }
            for index in range(FINAL_REWRITE_LIMIT)
        ]

        async def generate_variant(index: int) -> tuple[dict[str, Any], int]:
            nonlocal active_initial_calls, maximum_initial_concurrency
            variant_started = time.perf_counter()
            variant_schema: dict[str, Any] = {
                "rewrite": {
                    "title": REWRITE_STRATEGIES[index]["title"],
                    "script": length_guidance,
                    "used_source_fact_ids": ["正文实际使用的 source fact ID"],
                }
            }
            if index == 0:
                variant_schema["analysis"] = {
                    "topic": "视频核心主题",
                    "hook": "黄金开头",
                    "selling_points": ["至少四条"],
                    "structure": ["至少五段"],
                    "template": "可复用表达结构",
                    "core_points": ["完整核心观点"],
                    "arguments": ["来源支持的论据"],
                    "cases": ["原文案例；没有则空数组"],
                    "data_points": ["原文数据；没有则空数组"],
                }
            variant_payload = {
                **prompt_payload,
                "source_fact_ledger": source_fact_ledger,
                "variant_task": {
                    "index": index,
                    "title": REWRITE_STRATEGIES[index]["title"],
                    "angle": variant_requirements[index],
                    "target_center_chars": target_center_chars,
                },
                "requirements": [
                    *independent_base_requirements,
                    "这是单版本独立生成任务，不要生成或讨论其他版本，不得把篇幅分配给其他版本",
                    f"本版本瞄准 {target_center_chars} 个中文字符，并严格保持在 {minimum_chars}–{maximum_chars} 字",
                    "每一个数字、机构、时间、指标、案例、条件和风险限定都必须绑定 source_fact_ledger 中的 fact ID",
                    "只能使用来源事实账本中的事实；可以改变表达和顺序，但不得创造账本外证据",
                    "used_source_fact_ids 只列正文实际表达的 fact ID，不得虚报覆盖",
                ],
                "schema": variant_schema,
            }
            compact_variant_payload = {
                "content_input": analysis_input,
                "source_fact_ledger": source_fact_ledger,
                "variant_task": {
                    "index": index,
                    "title": REWRITE_STRATEGIES[index]["title"],
                    "angle": variant_requirements[index],
                },
                "length_target": {
                    "minimum_chars": minimum_chars,
                    "target_center_chars": target_center_chars,
                    "maximum_chars": maximum_chars,
                },
                "requirements": [
                    "只输出一个合法 JSON 对象，不输出分析过程、思考、解释、规则复述或 markdown",
                    "JSON 只能包含 rewrite；rewrite 只能包含 title、script、used_source_fact_ids",
                    "script 只写可以直接口播的最终正文，不写提纲、分析、标签或生成说明",
                    "只使用 source_fact_ledger 支持的事实，不新增数字、机构、时间、指标、案例或因果结论",
                    f"script 严格保持在 {minimum_chars}–{maximum_chars} 个中文字符，瞄准约 {target_center_chars} 字",
                    "保持本版本指定角度，句尾完整，不重复 CTA",
                ],
                "schema": {
                    "rewrite": {
                        "title": REWRITE_STRATEGIES[index]["title"],
                        "script": "最终口播正文",
                        "used_source_fact_ids": ["正文实际使用的 source fact ID"],
                    }
                },
            }
            state = version_states[index]
            attempt = 0
            network_retries_used = 0
            contract_regenerations_used = 0
            use_compact_regeneration = False
            pending_retry_delay: float | None = None
            while True:
                attempt += 1
                if pending_retry_delay is not None:
                    state["state"] = "retrying"
                    state["retry_delay_ms"] = round(pending_retry_delay * 1000)
                    await asyncio.sleep(pending_retry_delay)
                    pending_retry_delay = None

                attempt_started = time.perf_counter()
                attempt_record: dict[str, Any] = {
                    "attempt": attempt,
                    "mode": "compact_regeneration" if use_compact_regeneration else "initial",
                    "state": "running",
                    "started_at": datetime.now(UTC).isoformat(),
                }
                state["state"] = "running"
                state["attempts"].append(attempt_record)
                try:
                    async with initial_semaphore:
                        call_number = await llm_budget.reserve()
                        attempt_record["llm_call_number"] = call_number
                        async with concurrency_lock:
                            active_initial_calls += 1
                            maximum_initial_concurrency = max(
                                maximum_initial_concurrency,
                                active_initial_calls,
                            )
                        try:
                            response = await LLMProvider().generate_json(
                                system=(
                                    "只输出最终 JSON 和可直接朗读的口播正文；禁止输出分析、思考、规则复述或 markdown。"
                                    if use_compact_regeneration
                                    else (
                                        "你是来源约束的短视频口播编导。原始转写和来源事实账本是唯一事实来源。"
                                        f"独立完成一个{output_language}版本；不得生成其他版本。只输出合法 JSON。"
                                    )
                                ),
                                payload=(
                                    compact_variant_payload
                                    if use_compact_regeneration
                                    else variant_payload
                                ),
                                max_tokens=MAX_SUPPLEMENT_RESPONSE_TOKENS,
                                attempt_label=(
                                    f"variant_{index}_compact_regeneration"
                                    if use_compact_regeneration
                                    else f"variant_{index}_attempt_{attempt}"
                                ),
                                max_transport_attempts=1,
                                allow_format_repair=False,
                                thinking_mode="disabled",
                            )
                            rewrite = response.get("rewrite") if isinstance(response, dict) else None
                            script = rewrite.get("script") if isinstance(rewrite, dict) else None
                            if not isinstance(script, str) or not script.strip():
                                raise LLMProviderError(
                                    code="llm_json_missing_fields",
                                    message="AI 响应缺少必须字段 rewrite.script。",
                                    retryable=False,
                                    schema_error="missing_or_empty:rewrite.script",
                                    content_type="parsed_json",
                                )
                        finally:
                            async with concurrency_lock:
                                active_initial_calls -= 1
                except LLMProviderError as error:
                    network_retryable = _retryable_initial_provider_error(error)
                    application_contract_failure = error.code in {
                        "llm_empty_content",
                        "llm_empty_content_exhausted",
                        "llm_json_contract_error",
                        "llm_json_parse_error",
                        "llm_json_missing_fields",
                    }
                    can_compact_regenerate = (
                        application_contract_failure
                        and not use_compact_regeneration
                        and contract_regenerations_used
                        < SOURCE_INITIAL_MAX_EXHAUSTION_REGENERATIONS
                    )
                    effective_error_code = (
                        "llm_empty_content_exhausted"
                        if use_compact_regeneration and error.code == "llm_empty_content"
                        else error.code
                    )
                    can_network_retry = (
                        network_retryable
                        and not use_compact_regeneration
                        and network_retries_used < SOURCE_INITIAL_MAX_NETWORK_RETRIES
                    )
                    attempt_record.update(
                        {
                            "state": "failed",
                            "error_code": effective_error_code,
                            "error_type": type(error).__name__,
                            "retryable": can_compact_regenerate or can_network_retry,
                            "http_status": error.http_status,
                            "content_length": error.content_length,
                            "reasoning_content_length": error.reasoning_content_length,
                            "completion_tokens": error.completion_tokens,
                            "reasoning_tokens": error.reasoning_tokens,
                            "finish_reason": error.finish_reason,
                            "content_type": error.content_type,
                            "parser_repair_applied": error.parser_repair_applied,
                            "compact_regeneration_attempt": 1 if use_compact_regeneration else 0,
                            "elapsed_ms": round((time.perf_counter() - attempt_started) * 1000),
                        }
                    )
                    logger.warning(
                        "viral_variant request_id=%s index=%s attempt=%s state=failed "
                        "category=%s retryable=%s http_status=%s finish_reason=%s content_type=%s "
                        "content_length=%s parser_repair_applied=%s compact_regeneration_attempt=%s elapsed_ms=%s",
                        current_request_id(),
                        index,
                        attempt,
                        error.code,
                        attempt_record["retryable"],
                        error.http_status,
                        error.finish_reason or "none",
                        error.content_type,
                        error.content_length,
                        error.parser_repair_applied,
                        attempt_record["compact_regeneration_attempt"],
                        attempt_record["elapsed_ms"],
                    )
                    if can_compact_regenerate:
                        contract_regenerations_used += 1
                        state["compact_regenerations"] = contract_regenerations_used
                        state["retry_reason"] = error.code
                        state["state"] = "retrying"
                        use_compact_regeneration = True
                        continue
                    if can_network_retry:
                        network_retries_used += 1
                        state["network_retries"] = network_retries_used
                        state["retry_reason"] = error.code
                        state["state"] = "retrying"
                        pending_retry_delay = (
                            SOURCE_RETRY_BASE_DELAY_SECONDS * (2 ** (network_retries_used - 1))
                            + random.uniform(0.0, SOURCE_RETRY_JITTER_SECONDS)
                        )
                        continue
                    state["state"] = "failed"
                    state["error_code"] = effective_error_code
                    if effective_error_code != error.code:
                        error.code = effective_error_code
                    raise
                except _LLMCallBudgetExceeded:
                    attempt_record.update(
                        {
                            "state": "failed",
                            "error_code": "llm_call_budget_exhausted",
                            "error_type": "_LLMCallBudgetExceeded",
                            "retryable": False,
                            "elapsed_ms": round((time.perf_counter() - attempt_started) * 1000),
                        }
                    )
                    state["state"] = "failed"
                    state["error_code"] = "llm_call_budget_exhausted"
                    raise
                except Exception as error:
                    attempt_record.update(
                        {
                            "state": "failed",
                            "error_code": "unexpected_provider_error",
                            "error_type": type(error).__name__,
                            "retryable": False,
                            "elapsed_ms": round((time.perf_counter() - attempt_started) * 1000),
                        }
                    )
                    state["state"] = "failed"
                    state["error_code"] = "unexpected_provider_error"
                    raise

                attempt_record.update(
                    {
                        "state": "succeeded",
                        "elapsed_ms": round((time.perf_counter() - attempt_started) * 1000),
                    }
                )
                state["state"] = "succeeded"
                state["has_valid_response"] = True
                state["elapsed_ms"] = round((time.perf_counter() - variant_started) * 1000)
                logger.warning(
                    "viral_variant request_id=%s index=%s attempt=%s state=succeeded "
                    "llm_call_number=%s elapsed_ms=%s",
                    current_request_id(),
                    index,
                    attempt,
                    attempt_record["llm_call_number"],
                    attempt_record["elapsed_ms"],
                )
                return response, state["elapsed_ms"]

        initial_started = time.perf_counter()
        generated = await asyncio.gather(
            *(generate_variant(index) for index in range(FINAL_REWRITE_LIMIT)),
            return_exceptions=True,
        )
        llm_call_count = llm_budget.used_calls
        initial_elapsed_ms = round((time.perf_counter() - initial_started) * 1000)
        stage_timings.append(
            {
                "stage": "independent_initial",
                "elapsed_ms": initial_elapsed_ms,
                "variant_elapsed_ms": [
                    state.get("elapsed_ms")
                    for state in version_states
                ],
                "parallel": True,
                "concurrency_limit": SOURCE_INITIAL_CONCURRENCY,
                "maximum_observed_concurrency": maximum_initial_concurrency,
            }
        )
        failures = [
            {
                "index": index,
                "error_type": type(value).__name__,
                "error_code": (
                    value.code
                    if isinstance(value, LLMProviderError)
                    else version_states[index].get("error_code", "")
                ),
                "retryable": (
                    _retryable_initial_provider_error(value)
                    if isinstance(value, LLMProviderError)
                    else False
                ),
            }
            for index, value in enumerate(generated)
            if isinstance(value, BaseException)
        ]
        initial_generation_failures = failures
        independent_initial_results = [
            value[0] for value in generated if not isinstance(value, BaseException)
        ]
        all_initial_variants_failed = not independent_initial_results
        initial_variant_elapsed = [
            value[1] for value in generated if not isinstance(value, BaseException)
        ]
        stage_timings[-1]["variant_elapsed_ms"] = initial_variant_elapsed
        first_success = independent_initial_results[0] if independent_initial_results else {}
        first_analysis = first_success.get("analysis")
        data = first_analysis if isinstance(first_analysis, dict) else first_success
        if not data:
            data = dict(fallback_text)
        independent_rewrites: list[dict[str, Any]] = []
        for index, generated_value in enumerate(generated):
            response = (
                generated_value[0]
                if not isinstance(generated_value, BaseException)
                else {}
            )
            rewrite = response.get("rewrite")
            if not isinstance(rewrite, dict):
                legacy_rewrites = response.get("rewrites")
                rewrite = (
                    legacy_rewrites[index]
                    if isinstance(legacy_rewrites, list)
                    and index < len(legacy_rewrites)
                    and isinstance(legacy_rewrites[index], dict)
                    else {}
                )
            script = smooth_spoken_script(str(rewrite.get("script") or ""))
            used_ids = [
                str(item)
                for item in (rewrite.get("used_source_fact_ids") or [])
                if str(item) in source_fact_ids
            ]
            independent_rewrites.append(
                {
                    "title": REWRITE_STRATEGIES[index]["title"],
                    "script": script,
                    "used_source_fact_ids": list(dict.fromkeys(used_ids)),
                    "provenance": "independent_initial",
                }
            )
        if not independent_initial_results:
            independent_rewrites[0] = {
                "title": REWRITE_STRATEGIES[0]["title"],
                "script": _source_backed_scaffold(
                    source_fact_ledger=source_fact_ledger,
                    index=0,
                    minimum_chars=minimum_chars,
                    target_center_chars=target_center_chars,
                    maximum_chars=maximum_chars,
                ),
                "used_source_fact_ids": [],
                "provenance": "deterministic_scaffold",
            }
        data = {**data, "rewrites": independent_rewrites, "_independent_rewrites": independent_rewrites}
    else:
        initial_started = time.perf_counter()
        data = await LLMProvider().generate_json(
            system=(
                "你是短视频爆款文案拆解专家和数字人口播编导。"
                "你的任务是提炼结构和创作方法，并生成原创改写稿。"
                f"目标输出语言是{output_language}。除字段名外，所有内容必须使用{output_language}。只输出合法 JSON。"
            ),
            payload=prompt_payload,
            max_tokens=8000,
            thinking_mode="disabled",
        )
        llm_call_count += 1
        stage_timings.append(
            {
                "stage": "initial",
                "elapsed_ms": round((time.perf_counter() - initial_started) * 1000),
                "parallel": False,
            }
        )

    def normalize_analysis(payload: dict[str, Any]) -> dict[str, Any]:
        if source_scope == "public_metadata":
            payload = {**payload, "cases": [], "data_points": []}
        return validate_viral_analysis_payload(
        {
            "topic": payload.get("topic") or fallback_text["topic"],
            "hook": payload.get("hook") or fallback_text["hook"],
            "selling_points": payload.get("selling_points") or fallback_text["selling_points"],
            "structure": payload.get("structure") or fallback_text["structure"],
            "template": payload.get("template") or payload.get("template_formula") or fallback_text["template"],
            "rewrites": payload.get("rewrites") or payload.get("rewrite_versions") or payload.get("rewriteVersions") or payload.get("scripts"),
            "core_points": payload.get("core_points"),
            "arguments": payload.get("arguments"),
            "cases": payload.get("cases"),
            "data_points": payload.get("data_points"),
        },
        language=language,
        )

    def rewrite_lengths(payload: dict[str, Any]) -> list[int]:
        value = payload.get("rewrites") or payload.get("rewrite_versions") or payload.get("rewriteVersions") or payload.get("scripts") or []
        return [_cjk_len(str(item.get("script") or "")) for item in value[:FINAL_REWRITE_LIMIT] if isinstance(item, dict)]

    result = normalize_analysis(data)
    if source_scope == "full_content":
        # The legacy normalizer may replace a valid rewrite with a short local
        # diversity template. Independent generation already provides distinct
        # angles, so preserve those scripts and only apply deterministic cleanup.
        result = {**result, "rewrites": data["_independent_rewrites"]}
    minimum_rewrite_chars = minimum_chars
    normalized_lengths = [_cjk_len(item.get("script", "")) for item in result["rewrites"]]
    length_repair_rounds: list[dict[str, Any]] = [
        {"round": 0, "stage": "initial", "actual_chars": list(normalized_lengths)}
    ]
    logger.warning(
        "viral_rewrite_lengths request_id=%s attempt=initial source_scope=%s requested_length=%s effective_length=%s target_chars=%s raw_chars=%s normalized_chars=%s",
        current_request_id(),
        source_scope,
        rewrite_length,
        length_target.length_mode,
        minimum_rewrite_chars,
        rewrite_lengths(data),
        normalized_lengths,
    )
    # Retained for non-independent legacy callers only. Full-content requests
    # now use source-constrained repair after fact review, never free expansion.
    if (
        source_scope == "full_content"
        and not independent_initial_results
        and not all_initial_variants_failed
    ):
        overlong_indexes = [
            index for index, actual_chars in enumerate(normalized_lengths) if actual_chars > maximum_chars
        ]
        if overlong_indexes:
            compression = await LLMProvider().generate_json(
                system=(
                    "你是口播稿去重压缩编辑。只输出合法 JSON。"
                    "只能删除重复、空话和冗余表达，不得新增、篡改事实或硬截断句子。"
                ),
                payload={
                    "corrected_transcript": raw_script,
                    "length_target": length_target.diagnostics(),
                    "current_rewrites": [
                        {**result["rewrites"][index], "index": index}
                        for index in overlong_indexes
                    ],
                    "requirements": [
                        f"只处理列出的版本，将每条压缩到 {minimum_chars}–{maximum_chars} 个中文字符，瞄准约 {target_center_chars} 字",
                        "优先合并同义句，删除重复观点、重复CTA和没有信息量的过渡语",
                        "保留原转写中的事实、数字、案例、因果关系、限定条件和各版本原有角度",
                        "文案必须以完整句结束；禁止按字符硬截断",
                        "财经内容保持中性风险表达；情感内容保留短句、停顿和情绪递进",
                    ],
                    "schema": {
                        "compressions": [
                            {
                                "index": "与 current_rewrites.index 一致的整数",
                                "compressed_script": "压缩后的完整口播正文",
                            }
                        ]
                    },
                },
                max_tokens=MAX_SUPPLEMENT_RESPONSE_TOKENS,
                thinking_mode="disabled",
            )
            compression_values = compression.get("compressions")
            compression_values = compression_values if isinstance(compression_values, list) else []
            compressed_by_index = {
                item.get("index"): sanitize_rewrite_script(str(item.get("compressed_script") or ""))
                for item in compression_values
                if isinstance(item, dict) and item.get("index") in overlong_indexes
            }
            before_compression_lengths = list(normalized_lengths)
            compressed_rewrites = []
            for index, rewrite in enumerate(result["rewrites"]):
                compressed = compressed_by_index.get(index, "")
                compressed_rewrites.append(
                    {**rewrite, "script": smooth_spoken_script(compressed) if compressed else rewrite["script"]}
                )
            result = {**result, "rewrites": compressed_rewrites}
            normalized_lengths = [_cjk_len(item.get("script", "")) for item in result["rewrites"]]
            length_repair_rounds.append(
                {
                    "round": 1,
                    "stage": "compressing",
                    "requested_indexes": overlong_indexes,
                    "before_chars": before_compression_lengths,
                    "actual_chars": list(normalized_lengths),
                }
            )

        previous_round_by_index: dict[int, dict[str, int]] = {}
        for supplement_round in range(1, MAX_REWRITE_SUPPLEMENT_ROUNDS + 1):
            supplements_requested = []
            for index, (rewrite, actual_chars) in enumerate(zip(result["rewrites"], normalized_lengths, strict=True)):
                if actual_chars >= minimum_rewrite_chars:
                    continue
                gap_chars = minimum_rewrite_chars - actual_chars
                previous = previous_round_by_index.get(index, {})
                target_additional_chars, planning_yield = _planned_supplement_chars(
                    current_chars=actual_chars,
                    desired_final_chars=target_center_chars,
                    supplement_round=supplement_round,
                    previous_requested_chars=previous.get("requested_chars"),
                    previous_returned_chars=previous.get("returned_chars"),
                )
                supplements_requested.append(
                    {
                        "index": index,
                        "title": rewrite["title"],
                        "current_chars": actual_chars,
                        "gap_chars": gap_chars,
                        "desired_final_chars": target_center_chars,
                        "planning_yield_rate": round(planning_yield, 4),
                        "target_additional_chars": target_additional_chars,
                        "maximum_additional_chars": MAX_REQUESTED_ADDITIONAL_CJK_CHARS,
                    }
                )
            if not supplements_requested:
                break

            expansion = await LLMProvider().generate_json(
                system=(
                    "你是口播稿定向扩写编辑。只输出合法 JSON。"
                    "只能使用转写稿和已有拆解中明确出现的事实，不得新增数字、机构、案例、政策或观点。"
                ),
                payload={
                    "corrected_transcript": raw_script,
                    "analysis": {
                        "topic": result["topic"],
                        "core_points": result["core_points"],
                        "arguments": result["arguments"],
                        "cases": result["cases"],
                        "data_points": result["data_points"],
                    },
                    "current_rewrites": result["rewrites"],
                    "supplement_round": supplement_round,
                    "maximum_supplement_rounds": MAX_REWRITE_SUPPLEMENT_ROUNDS,
                    "supplements_requested": supplements_requested,
                    "requirements": [
                        "只为 supplements_requested 中列出的版本生成接在现有正文末尾的扩写段落，不得重写、缩短或返回完整原稿",
                        "每个版本独立扩写；additional_script 以 target_additional_chars 为生成目标，不要在合并后刚到下限时提前结束",
                        f"扩写指向合并后约 {target_center_chars} 个中文字符；后端会在完整句边界控制最终不超过 {maximum_chars} 字",
                        f"任何单条 additional_script 不得超过 {MAX_REQUESTED_ADDITIONAL_CJK_CHARS} 个中文字符",
                        "只补原转写中已有、但当前版本尚未表达的信息；可展开其因果解释、适用条件、已有例子、风险与误区、可执行建议",
                        "优先覆盖转写稿中的主要观点、论据、案例、数据和行动建议，不要求五类内容机械平均分配",
                        "保留转写稿中的主要事实、数据、案例、论证顺序和限定条件",
                        "不得复述已有句子，不得用空话、同义改写或机械重复凑字数，不得新增转写稿中不存在的信息",
                        "禁止虚构公司案例及结果；禁止新增完成比例、持续周期、涨跌结果、ROE、股东名单、ETF份额、连续超预期或目标价调整",
                        "如果原转写没有足够事实可补，只能展开原有事实的限定条件和判断方法，不得用新证据补足长度",
                        "扩写段必须自然承接对应现有正文，保持该版本原有角度和口播风格",
                        "不得重复已有行动号召，不得在扩写段增加第二个CTA",
                        "扩写段使用完整口播句子并以句末标点收束，便于在上限内按完整句边界合并",
                    ],
                    "schema": {
                        "supplements": [
                            {
                                "index": "与 supplements_requested.index 完全一致的整数",
                                "title": "对应版本标题",
                                "additional_script": "只含需要追加的新口播正文",
                            }
                        ]
                    },
                },
                max_tokens=MAX_SUPPLEMENT_RESPONSE_TOKENS,
                thinking_mode="disabled",
            )
            requested_indexes = {item["index"] for item in supplements_requested}
            supplements_value = expansion.get("supplements")
            supplements_value = supplements_value if isinstance(supplements_value, list) else []
            supplements_by_index = {
                item.get("index"): str(item.get("additional_script") or "").strip()
                for item in supplements_value
                if (
                    isinstance(item, dict)
                    and isinstance(item.get("index"), int)
                    and item.get("index") in requested_indexes
                )
            }
            before_round_lengths = list(normalized_lengths)
            merged_rewrites = []
            for index, rewrite in enumerate(result["rewrites"]):
                supplement = supplements_by_index.get(index, "")
                merged_rewrites.append(
                    {
                        "title": rewrite["title"],
                        "script": (
                            smooth_spoken_script(_join_sentences(rewrite["script"], supplement))
                            if supplement
                            else rewrite["script"]
                        ),
                    }
                )
            # The initial rewrites have already been normalized and diversified.
            # Preserve them and sanitize only the appended continuation.
            result = {**result, "rewrites": merged_rewrites}
            normalized_lengths = [_cjk_len(item.get("script", "")) for item in result["rewrites"]]
            returned_chars_by_index = {
                item["index"]: _cjk_len(supplements_by_index.get(item["index"], ""))
                for item in supplements_requested
            }
            round_items = []
            for item in supplements_requested:
                index = item["index"]
                returned_chars = returned_chars_by_index[index]
                previous_round_by_index[index] = {
                    "requested_chars": item["target_additional_chars"],
                    "returned_chars": returned_chars,
                }
                round_items.append(
                    {
                        "index": index,
                        "before_chars": before_round_lengths[index],
                        "gap_chars": item["gap_chars"],
                        "desired_final_chars": item["desired_final_chars"],
                        "planning_yield_rate": item["planning_yield_rate"],
                        "requested_additional_chars": item["target_additional_chars"],
                        "returned_additional_chars": returned_chars,
                        "merged_chars": normalized_lengths[index],
                    }
                )
            length_repair_rounds.append(
                {
                    "round": supplement_round,
                    "stage": "expanding",
                    "items": round_items,
                    "actual_chars": list(normalized_lengths),
                }
            )
            logger.warning(
                "viral_rewrite_lengths request_id=%s attempt=supplement_%s source_scope=%s requested_length=%s effective_length=%s "
                "target_chars=%s desired_final_chars=%s requested_indexes=%s gaps=%s planning_yield_rates=%s "
                "target_additional_chars=%s initial_chars=%s supplement_chars=%s normalized_chars=%s",
                current_request_id(),
                supplement_round,
                source_scope,
                rewrite_length,
                length_target.length_mode,
                minimum_rewrite_chars,
                target_center_chars,
                [item["index"] for item in supplements_requested],
                [item["gap_chars"] for item in supplements_requested],
                [item["planning_yield_rate"] for item in supplements_requested],
                [item["target_additional_chars"] for item in supplements_requested],
                before_round_lengths,
                [returned_chars_by_index[item["index"]] for item in supplements_requested],
                normalized_lengths,
            )

    if any(length > maximum_chars for length in normalized_lengths):
        before_trim_lengths = list(normalized_lengths)
        result = {
            **result,
            "rewrites": [
                {
                    **rewrite,
                    "script": _trim_to_sentence_boundary(
                        rewrite["script"],
                        minimum_chars=minimum_rewrite_chars,
                        maximum_chars=maximum_chars,
                    ),
                }
                for rewrite in result["rewrites"]
            ],
        }
        normalized_lengths = [_cjk_len(item.get("script", "")) for item in result["rewrites"]]
        length_repair_rounds.append(
            {
                "round": len(length_repair_rounds),
                "stage": "sentence_boundary_trim",
                "before_chars": before_trim_lengths,
                "actual_chars": list(normalized_lengths),
            }
        )
        logger.warning(
            "viral_rewrite_lengths request_id=%s attempt=sentence_boundary_trim target_chars=%s maximum_chars=%s normalized_chars=%s",
            current_request_id(),
            minimum_rewrite_chars,
            maximum_chars,
            normalized_lengths,
        )
    hard_violations_before = [
        unsupported_hard_facts(raw_script, rewrite["script"])
        for rewrite in result["rewrites"]
    ]
    requires_fact_review = (
        source_scope == "full_content"
        and not all_initial_variants_failed
        and not initial_generation_failures
    )
    invalid_lengths = [length for length in normalized_lengths if length < minimum_rewrite_chars or length > maximum_chars]
    if invalid_lengths and source_scope != "full_content":
        actual_chars_text = " / ".join(str(length) for length in normalized_lengths)
        raise HTTPException(
            status_code=502,
            detail={
                "code": "analysis_output_out_of_range",
                "stage": "rewriting",
                "message": (
                    f"AI 改写长度未达到 {minimum_rewrite_chars}–{maximum_chars} 个中文字符；"
                    f"实际为 {actual_chars_text}。"
                ),
                "retryable": False,
                "target_chars": minimum_rewrite_chars,
                "target_center_chars": target_center_chars,
                "maximum_chars": maximum_chars,
                "actual_chars": normalized_lengths,
                "length_unit": "cjk_chars",
                **length_target.diagnostics(),
                "length_repair_rounds": length_repair_rounds,
                "resource_limits": {
                    "maximum_supplement_rounds": MAX_REWRITE_SUPPLEMENT_ROUNDS,
                    "maximum_requested_additional_chars": MAX_REQUESTED_ADDITIONAL_CJK_CHARS,
                    "maximum_supplement_response_tokens": MAX_SUPPLEMENT_RESPONSE_TOKENS,
                    "maximum_final_chars": maximum_chars,
                },
            },
        )

    fact_fidelity_diagnostic: dict[str, Any] = {
        "required": False,
        "reviewed": False,
        "hard_violations_before": [],
        "hard_violations_after": [],
        "removed_claims": [],
        "unsupported_remaining": [],
        "source_constrained_repairs": [],
        "final_source_reconstruction": [],
    }
    primary_selection_diagnostic: dict[str, Any] = {}
    primary_model_rewrite_succeeded = False
    minimum_fact_coverage_count = min(
        source_fact_ledger.get("fact_count", 0),
        max(
            1,
            math.ceil(
                source_fact_ledger.get("fact_count", 0)
                * MIN_SOURCE_FACT_COVERAGE_RATE
            ),
        ),
    )
    fact_fidelity_diagnostic["required"] = requires_fact_review
    fact_fidelity_diagnostic["hard_violations_before"] = hard_violations_before

    if requires_fact_review:
        fact_review_started = time.perf_counter()
        try:
            fact_review_call_number = await llm_budget.reserve()
        except _LLMCallBudgetExceeded:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "analysis_llm_call_budget_exhausted",
                    "stage": "fact_review",
                    "message": "模型调用已达到请求级资源上限。",
                    "retryable": False,
                    "actual_chars": normalized_lengths,
                    "stage_timings": stage_timings,
                    "llm_call_count": llm_budget.used_calls,
                    "maximum_llm_calls": MAX_SOURCE_CONSTRAINED_LLM_CALLS,
                },
            )
        fact_review = await LLMProvider().generate_json(
            system=(
                "你是严格的来源事实审校编辑。原始转写是唯一事实来源。"
                "你的任务是删除或改写无来源事实，不是创作新内容。只输出合法 JSON。"
            ),
            payload={
                "corrected_transcript": raw_script,
                "source_fact_ledger": source_fact_ledger,
                "current_rewrites": [
                    {**rewrite, "index": index}
                    for index, rewrite in enumerate(result["rewrites"])
                ],
                "hard_violations": [
                    {"index": index, "items": items}
                    for index, items in enumerate(hard_violations_before)
                    if items
                ],
                "length_target": {
                    "minimum_chars": minimum_rewrite_chars,
                    "center_chars": target_center_chars,
                    "maximum_chars": maximum_chars,
                    "unit": "cjk_chars",
                },
                "requirements": [
                    "逐条核对机构、公司、人物、案例、指标、数字、百分比、日期、时间范围、具体数量和确定性因果",
                    "只允许使用原始转写明确出现的事实；不得把拆解字段或现有改写中的内容反向当作来源证据",
                    "删除或改回一般性表述时，必须保持原版本角度和口播风格，并尽量只做必要修改",
                    "对每个 unsupported span 优先用语义最接近的来源事实替换，不能只删除整段",
                    "used_source_fact_ids 必须只列 audited_script 实际覆盖的事实，且只能取自 source_fact_ledger.fact_ids",
                    "一般性解释必须明确写成判断方法、可能性或待核对条件，不能声称某公司或机构已经发生了原文未提及的行为或结果",
                    "禁止“举个例子”后虚构公司、完成比例、持续周期、涨跌结果或因果结果",
                    "禁止新增原文没有的ROE、股东名单、ETF份额、连续增长、连续超预期、目标价调整等证据",
                    "财经内容必须保留“不是确定性买入信号”等中性风险边界，不得给出确定性买入、卖出或收益承诺",
                    f"每条 audited_script 必须保持在 {minimum_rewrite_chars}–{maximum_chars} 个中文字符，并以完整句结束",
                    "removed_unsupported_claims 必须逐项列出从 current_rewrites 删除或改写的原始片段及原因",
                    "审校后的文本不得为了补足长度创造任何新事实；若只能用空话或新证据补足，unsupported_remaining 必须为 true",
                ],
                "schema": {
                    "reviews": [
                        {
                            "index": "与 current_rewrites.index 一致的整数",
                            "audited_script": "完成事实审校后的完整口播正文",
                            "removed_unsupported_claims": [
                                {
                                    "span": "从 current_rewrites 原样摘录的无来源片段",
                                    "category": "数字/时间/机构/案例/指标/因果",
                                    "reason": "原始转写不支持该内容",
                                }
                            ],
                            "unsupported_remaining": False,
                            "unsupported_spans": [
                                {
                                    "span": "仍无来源支持的原文片段；没有则空数组",
                                    "reason": "为何不受来源支持",
                                }
                            ],
                            "used_source_fact_ids": ["审校后正文实际覆盖的 source fact ID"],
                        }
                    ]
                },
            },
            max_tokens=MAX_SUPPLEMENT_RESPONSE_TOKENS,
            attempt_label=f"fact_review_call_{fact_review_call_number}",
            max_transport_attempts=1,
            allow_format_repair=False,
            thinking_mode="disabled",
        )
        llm_call_count = llm_budget.used_calls
        stage_timings.append(
            {
                "stage": "fact_review",
                "elapsed_ms": round((time.perf_counter() - fact_review_started) * 1000),
                "parallel": False,
            }
        )
        reviews_value = fact_review.get("reviews")
        reviews_value = reviews_value if isinstance(reviews_value, list) else []
        reviews_by_index = {
            item.get("index"): item
            for item in reviews_value
            if isinstance(item, dict)
            and isinstance(item.get("index"), int)
            and 0 <= item["index"] < len(result["rewrites"])
        }
        if set(reviews_by_index) != set(range(len(result["rewrites"]))):
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "analysis_fact_fidelity_failed",
                    "stage": "fact_review",
                    "message": "事实保真审查返回字段不完整。",
                    "retryable": True,
                    "actual_chars": normalized_lengths,
                    "target_chars": minimum_rewrite_chars,
                    "target_min_chars": minimum_rewrite_chars,
                    "target_center_chars": target_center_chars,
                    "maximum_chars": maximum_chars,
                },
            )

        audited_rewrites = []
        removed_claims: list[list[dict[str, str]]] = []
        unsupported_spans: list[list[dict[str, str]]] = []
        used_source_fact_ids: list[list[str]] = []
        unsupported_remaining: list[int] = []
        for index, rewrite in enumerate(result["rewrites"]):
            review = reviews_by_index[index]
            audited_script = smooth_spoken_script(str(review.get("audited_script") or ""))
            reviewed_ids = [
                str(item)
                for item in (review.get("used_source_fact_ids") or rewrite.get("used_source_fact_ids") or [])
                if str(item) in source_fact_ids
            ]
            audited_rewrites.append(
                {
                    **rewrite,
                    "script": audited_script,
                    "used_source_fact_ids": list(dict.fromkeys(reviewed_ids)),
                    "provenance": (
                        "fact_review"
                        if _normalize_for_similarity(audited_script)
                        != _normalize_for_similarity(str(rewrite.get("script") or ""))
                        else rewrite.get("provenance", "independent_initial")
                    ),
                }
            )
            claims = review.get("removed_unsupported_claims")
            removed_claims.append(
                [
                    {
                        "span": str(claim.get("span") or "")[:240],
                        "category": str(claim.get("category") or "")[:80],
                        "reason": str(claim.get("reason") or "")[:240],
                    }
                    for claim in (claims if isinstance(claims, list) else [])
                    if isinstance(claim, dict)
                ]
            )
            spans = review.get("unsupported_spans")
            unsupported_spans.append(
                [
                    {
                        "span": str(item.get("span") or "")[:240],
                        "reason": str(item.get("reason") or "")[:240],
                    }
                    for item in (spans if isinstance(spans, list) else [])
                    if isinstance(item, dict) and str(item.get("span") or "").strip()
                ]
            )
            used_source_fact_ids.append(list(dict.fromkeys(reviewed_ids)))
            if review.get("unsupported_remaining") is not False:
                unsupported_remaining.append(index)

        result = {**result, "rewrites": audited_rewrites}
        normalized_lengths = [_cjk_len(item.get("script", "")) for item in result["rewrites"]]
        hard_violations_after = [
            unsupported_hard_facts(raw_script, rewrite["script"])
            for rewrite in result["rewrites"]
        ]
        verified_fact_coverage = [
            map_source_fact_coverage(
                source_fact_ledger,
                rewrite["script"],
                claimed_fact_ids=list(rewrite.get("used_source_fact_ids") or []),
            )
            for rewrite in result["rewrites"]
        ]
        fact_fidelity_diagnostic.update(
            {
                "reviewed": True,
                "hard_violations_after": hard_violations_after,
                "removed_claims": removed_claims,
                "unsupported_spans": unsupported_spans,
                "used_source_fact_ids": used_source_fact_ids,
                "verified_fact_coverage": verified_fact_coverage,
                "unsupported_remaining": unsupported_remaining,
            }
        )
        logger.warning(
            "viral_fact_fidelity request_id=%s reviewed=true removed_counts=%s hard_before_counts=%s "
            "hard_after_counts=%s unsupported_remaining=%s normalized_chars=%s",
            current_request_id(),
            [len(items) for items in removed_claims],
            [len(items) for items in hard_violations_before],
            [len(items) for items in hard_violations_after],
            unsupported_remaining,
            normalized_lengths,
        )
        reviewed_snapshots = [
            _candidate_quality_snapshot(
                index=index,
                rewrite=rewrite,
                raw_script=raw_script,
                source_fact_ledger=source_fact_ledger,
                minimum_chars=minimum_rewrite_chars,
                maximum_chars=maximum_chars,
                minimum_fact_coverage_count=minimum_fact_coverage_count,
            )
            for index, rewrite in enumerate(result["rewrites"])
        ]
        ranked_primary = sorted(
            reviewed_snapshots,
            key=lambda item: _primary_rank(
                item,
                minimum_chars=minimum_rewrite_chars,
                maximum_chars=maximum_chars,
            ),
        )
        primary_snapshot = ranked_primary[0]
        primary_index = int(primary_snapshot["index"])
        primary_model_rewrite_succeeded = bool(primary_snapshot["valid"])
        primary_attempts: list[dict[str, Any]] = []
        micro_gap_diagnostic: dict[str, Any] = {
            "attempted": False,
            "succeeded": False,
            "selected_index": primary_index,
            "before": _candidate_diagnostic_record(primary_snapshot),
        }
        primary_selection_diagnostic = {
            "selected_index": primary_index,
            "ranking": [
                {
                    "index": int(item["index"]),
                    "hard_violation_count": len(item["hard_violations"]),
                    "actual_chars": int(item["actual_chars"]),
                    "source_fact_coverage_count": int(item["coverage"]["used_count"]),
                    "complete_ending": "incomplete_ending" not in item["reasons"],
                    "reasons": list(item["reasons"]),
                }
                for item in ranked_primary
            ],
            "attempts": primary_attempts,
            "micro_gap_rescue": micro_gap_diagnostic,
        }

        micro_gap_eligible = _is_length_only_micro_gap_rescue_eligible(
            primary_snapshot,
            minimum_fact_coverage_count=minimum_fact_coverage_count,
            is_primary=True,
        )
        if micro_gap_eligible:
            micro_gap_diagnostic["attempted"] = True
            closing = _neutral_micro_gap_closing(
                industry=industry,
                raw_script=raw_script,
            )
            current_rewrite = result["rewrites"][primary_index]
            rescued_rewrite = {
                **current_rewrite,
                "script": f"{str(current_rewrite.get('script') or '').rstrip()}{closing}",
                "provenance": "model_rewrite_with_neutral_closing",
            }
            rescued_snapshot = _candidate_quality_snapshot(
                index=primary_index,
                rewrite=rescued_rewrite,
                raw_script=raw_script,
                source_fact_ledger=source_fact_ledger,
                minimum_chars=minimum_rewrite_chars,
                maximum_chars=maximum_chars,
                minimum_fact_coverage_count=minimum_fact_coverage_count,
            )
            micro_gap_diagnostic.update(
                {
                    "closing_chars": _cjk_len(closing),
                    "after": _candidate_diagnostic_record(rescued_snapshot),
                    "succeeded": bool(rescued_snapshot["valid"]),
                }
            )
            if rescued_snapshot["valid"]:
                result["rewrites"][primary_index] = rescued_rewrite
                primary_snapshot = rescued_snapshot
                primary_model_rewrite_succeeded = True
                normalized_lengths[primary_index] = rescued_snapshot["actual_chars"]
                hard_violations_after[primary_index] = list(
                    rescued_snapshot["hard_violations"]
                )
                verified_fact_coverage[primary_index] = dict(
                    rescued_snapshot["coverage"]
                )
                fact_fidelity_diagnostic["hard_violations_after"] = hard_violations_after
                fact_fidelity_diagnostic["verified_fact_coverage"] = verified_fact_coverage
            else:
                micro_gap_diagnostic["failure_reasons"] = list(
                    rescued_snapshot["exact_failure_reasons"]
                )

        if not primary_model_rewrite_succeeded:
            generation_floor = (
                max(minimum_rewrite_chars, 720)
                if maximum_chars >= 720
                else minimum_rewrite_chars
            )
            generation_target_low = (
                min(maximum_chars, max(generation_floor, 780))
                if maximum_chars >= 720
                else target_center_chars
            )
            generation_target_high = (
                min(maximum_chars, 820)
                if maximum_chars >= 720
                else maximum_chars
            )
            for attempt in range(1, PRIMARY_CONVERGENCE_MAX_CALLS + 1):
                if (
                    MAX_SOURCE_CONSTRAINED_LLM_CALLS - llm_budget.used_calls
                    <= SCAFFOLD_POLISH_RESERVED_CALLS
                ):
                    primary_attempts.append(
                        {"attempt": attempt, "outcome": "reserved_for_scaffold_polish"}
                    )
                    break
                current_rewrite = result["rewrites"][primary_index]
                current_snapshot = _candidate_quality_snapshot(
                    index=primary_index,
                    rewrite=current_rewrite,
                    raw_script=raw_script,
                    source_fact_ledger=source_fact_ledger,
                    minimum_chars=minimum_rewrite_chars,
                    maximum_chars=maximum_chars,
                    minimum_fact_coverage_count=minimum_fact_coverage_count,
                )
                unused_ids = list(current_snapshot["coverage"]["unused_source_fact_ids"])
                convergence_started = time.perf_counter()
                try:
                    call_number = await llm_budget.reserve()
                    response = await LLMProvider().generate_json(
                        system=(
                            "你是来源约束的主稿收敛编辑。原始转写和事实账本是唯一事实来源。"
                            "输出完整替换稿，不得追加补丁，不得自由扩写。只输出最小合法 JSON。"
                        ),
                        payload={
                            "primary_convergence": True,
                            "corrected_transcript": raw_script,
                            "source_fact_ledger": source_fact_ledger,
                            "variant": {
                                "index": primary_index,
                                "title": current_rewrite["title"],
                                "angle": variant_requirements[primary_index],
                            },
                            "current_script": current_rewrite["script"],
                            "current_chars": current_snapshot["actual_chars"],
                            "used_source_fact_ids": current_snapshot["coverage"][
                                "directly_supported_fact_ids"
                            ],
                            "unused_source_fact_ids": unused_ids,
                            "length_target": {
                                "validation_minimum_chars": minimum_rewrite_chars,
                                "generation_minimum_chars": generation_floor,
                                "generation_target_low": generation_target_low,
                                "generation_target_high": generation_target_high,
                                "maximum_chars": maximum_chars,
                                "unit": "cjk_chars",
                            },
                            "requirements": [
                                "优先恢复尚未表达的来源事实，保持原版本角度并形成自然连续的知识口播",
                                f"内部生成至少 {generation_floor} CJK，瞄准 {generation_target_low}–{generation_target_high} CJK",
                                "只允许使用 corrected_transcript 和 source_fact_ledger 中已有的事实",
                                "禁止新增数字、机构、日期、周期、案例、指标或因果结论",
                                "必须返回完整替换稿，不得返回追加段落或修改说明",
                                "句尾完整、内部不重复；超过上限时只能按完整句边界收敛，禁止字符硬截断",
                                "used_source_fact_ids只列正文实际表达的事实ID",
                            ],
                            "schema": {
                                "title": "主稿标题",
                                "script": "完整替换口播正文",
                                "used_source_fact_ids": ["正文实际使用的来源事实ID"],
                            },
                        },
                        max_tokens=MAX_SUPPLEMENT_RESPONSE_TOKENS,
                        attempt_label=f"primary_convergence_{primary_index}_{attempt}_call_{call_number}",
                        max_transport_attempts=1,
                        allow_format_repair=False,
                        thinking_mode="disabled",
                    )
                    converged_script = smooth_spoken_script(
                        str(
                            response.get("script")
                            or response.get("repaired_script")
                            or response.get("reconstructed_script")
                            or ""
                        )
                    )
                    if _cjk_len(converged_script) > maximum_chars:
                        converged_script = _trim_to_sentence_boundary(
                            converged_script,
                            minimum_chars=minimum_rewrite_chars,
                            maximum_chars=maximum_chars,
                        )
                    converged_rewrite = {
                        **current_rewrite,
                        "title": str(response.get("title") or current_rewrite["title"]),
                        "script": converged_script,
                        "used_source_fact_ids": [
                            str(item)
                            for item in (response.get("used_source_fact_ids") or [])
                            if str(item) in source_fact_ids
                        ],
                        "provenance": "source_constrained_repair",
                    }
                    converged_snapshot = _candidate_quality_snapshot(
                        index=primary_index,
                        rewrite=converged_rewrite,
                        raw_script=raw_script,
                        source_fact_ledger=source_fact_ledger,
                        minimum_chars=minimum_rewrite_chars,
                        maximum_chars=maximum_chars,
                        minimum_fact_coverage_count=minimum_fact_coverage_count,
                    )
                    primary_attempts.append(
                        {
                            "attempt": attempt,
                            "outcome": "converged" if converged_snapshot["valid"] else "invalid",
                            "actual_chars": converged_snapshot["actual_chars"],
                            "reasons": converged_snapshot["reasons"],
                            "candidate_diagnostic": _candidate_diagnostic_record(
                                converged_snapshot
                            ),
                            "elapsed_ms": round((time.perf_counter() - convergence_started) * 1000),
                        }
                    )
                    result["rewrites"][primary_index] = converged_rewrite
                    primary_snapshot = converged_snapshot
                    if converged_snapshot["valid"]:
                        primary_model_rewrite_succeeded = True
                        break
                except (LLMProviderError, _LLMCallBudgetExceeded) as error:
                    primary_attempts.append(
                        {
                            "attempt": attempt,
                            "outcome": "provider_error",
                            "error_type": type(error).__name__,
                            "elapsed_ms": round((time.perf_counter() - convergence_started) * 1000),
                        }
                    )
                except Exception as error:
                    primary_attempts.append(
                        {
                            "attempt": attempt,
                            "outcome": "invalid_response",
                            "error_type": type(error).__name__,
                            "elapsed_ms": round((time.perf_counter() - convergence_started) * 1000),
                        }
                    )
            normalized_lengths = [_cjk_len(item.get("script", "")) for item in result["rewrites"]]
            hard_violations_after = [
                unsupported_hard_facts(raw_script, rewrite["script"])
                for rewrite in result["rewrites"]
            ]
            verified_fact_coverage = [
                map_source_fact_coverage(
                    source_fact_ledger,
                    rewrite["script"],
                    claimed_fact_ids=list(rewrite.get("used_source_fact_ids") or []),
                )
                for rewrite in result["rewrites"]
            ]
        primary_selection_diagnostic["succeeded"] = primary_model_rewrite_succeeded
        primary_selection_diagnostic["final_actual_chars"] = _cjk_len(
            result["rewrites"][primary_index]["script"]
        )
        fact_fidelity_diagnostic["primary_selection"] = primary_selection_diagnostic
        stage_timings.append(
            {
                "stage": "primary_convergence",
                "selected_index": primary_index,
                "attempt_count": len(
                    [item for item in primary_attempts if "actual_chars" in item]
                ),
                "succeeded": primary_model_rewrite_succeeded,
            }
        )
        invalid_after_fact_review = [
            length for length in normalized_lengths
            if length < minimum_rewrite_chars or length > maximum_chars
        ]
        repair_indexes = [
            index
            for index, length in enumerate(normalized_lengths)
            if (
                length < minimum_rewrite_chars
                or length > maximum_chars
                or bool(hard_violations_after[index])
                or index in unsupported_remaining
                or bool(unsupported_spans[index])
            )
        ]
        if primary_model_rewrite_succeeded:
            repair_indexes = [index for index in repair_indexes if index != primary_index]
        else:
            repair_indexes = []
        repair_diagnostics: list[dict[str, Any]] = []
        repair_failed_indexes: list[int] = []
        repair_no_progress_indexes: list[int] = []
        if repair_indexes:
            async def repair_variant(index: int) -> tuple[int, dict[str, Any], int]:
                nonlocal active_initial_calls, maximum_initial_concurrency
                repair_started = time.perf_counter()
                rewrite = result["rewrites"][index]
                used_ids = list(
                    verified_fact_coverage[index]["directly_supported_fact_ids"]
                )
                unused_ids = [fact_id for fact_id in source_fact_ledger["fact_ids"] if fact_id not in used_ids]
                async with initial_semaphore:
                    call_number = await llm_budget.reserve()
                    async with concurrency_lock:
                        active_initial_calls += 1
                        maximum_initial_concurrency = max(
                            maximum_initial_concurrency,
                            active_initial_calls,
                        )
                    try:
                        response = await LLMProvider().generate_json(
                            system=(
                                "你是来源约束的口播修复编辑。原始转写和来源事实账本是唯一事实来源。"
                                "必须用来源事实替换违规内容；禁止自由扩写。只输出合法 JSON。"
                            ),
                            payload={
                        "corrected_transcript": raw_script,
                        "source_fact_ledger": source_fact_ledger,
                        "variant": {
                            "index": index,
                            "title": rewrite["title"],
                            "angle": variant_requirements[index],
                        },
                        "current_script": rewrite["script"],
                        "current_chars": normalized_lengths[index],
                        "unsupported_spans": unsupported_spans[index],
                        "hard_violations": hard_violations_after[index],
                        "used_source_fact_ids": used_ids,
                        "unused_source_fact_ids": unused_ids,
                        "length_target": {
                            "minimum_chars": minimum_rewrite_chars,
                            "center_chars": target_center_chars,
                            "maximum_chars": maximum_chars,
                            "unit": "cjk_chars",
                        },
                        "requirements": [
                            "逐个将 unsupported_spans 和 hard_violations 替换为语义最接近的来源事实，不得只删除整段",
                            "长度不足时只能补充 unused_source_fact_ids 对应的来源事实，优先限定条件、因果边界、风险说明和不同信号的区别",
                            "不得机械重复 already used 的 source fact，不得重复 CTA",
                            "如果来源事实已全部覆盖仍不足，只能增加不含新事实主张的过渡、结构提示和明确标注为判断方法的解释",
                            "禁止新增数字、百分比、日期、周期、数量、机构、公司、人物、案例、指标或确定性因果",
                            "禁止80%、ROE、股东名单、ETF份额增长、连续季度、同比、虚构公司案例和结果，除非账本原文明确存在",
                            f"最终完整正文必须在 {minimum_rewrite_chars}–{maximum_chars} CJK，瞄准约 {target_center_chars}，并以完整句结束",
                            "保持本版本角度；财经内容保留中性风险边界，不给确定性买卖或收益承诺",
                            "used_source_fact_ids 只能列最终正文实际表达的账本 ID；unsupported_spans 必须列出仍无法修复的片段",
                        ],
                        "schema": {
                            "repaired_script": "替换并补全后的完整口播正文",
                            "used_source_fact_ids": ["最终正文实际覆盖的 source fact ID"],
                            "replacements": [
                                {
                                    "unsupported_span": "被替换的原片段",
                                    "replacement_source_fact_id": "用于替换的 source fact ID",
                                }
                            ],
                            "unsupported_spans": [],
                            "unsupported_remaining": False,
                        },
                            },
                            max_tokens=MAX_SUPPLEMENT_RESPONSE_TOKENS,
                            attempt_label=f"source_repair_{index}_call_{call_number}",
                            max_transport_attempts=1,
                            allow_format_repair=False,
                            thinking_mode="disabled",
                        )
                    finally:
                        async with concurrency_lock:
                            active_initial_calls -= 1
                return index, response, round((time.perf_counter() - repair_started) * 1000)

            repair_started = time.perf_counter()
            repair_results = await asyncio.gather(
                *(repair_variant(index) for index in repair_indexes),
                return_exceptions=True,
            )
            llm_call_count = llm_budget.used_calls
            variant_elapsed_ms: list[int | None] = []
            repaired_rewrites = list(result["rewrites"])
            for expected_index, value in zip(repair_indexes, repair_results, strict=True):
                if isinstance(value, BaseException):
                    repair_failed_indexes.append(expected_index)
                    variant_elapsed_ms.append(None)
                    repair_diagnostics.append(
                        {
                            "index": expected_index,
                            "outcome": "provider_error",
                            "error_type": type(value).__name__,
                        }
                    )
                    continue
                index, response, elapsed_ms = value
                variant_elapsed_ms.append(elapsed_ms)
                repaired_script = smooth_spoken_script(str(response.get("repaired_script") or ""))
                repaired_script = _trim_to_sentence_boundary(
                    repaired_script,
                    minimum_chars=minimum_rewrite_chars,
                    maximum_chars=maximum_chars,
                )
                repaired_ids = [
                    str(item)
                    for item in (response.get("used_source_fact_ids") or [])
                    if str(item) in source_fact_ids
                ]
                remaining_spans = response.get("unsupported_spans")
                remaining_spans = (
                    [item for item in remaining_spans if isinstance(item, dict)]
                    if isinstance(remaining_spans, list)
                    else [{"span": "", "reason": "missing_unsupported_spans"}]
                )
                unsupported_flag = response.get("unsupported_remaining") is not False or bool(remaining_spans)
                no_progress = bool(
                    repaired_script
                    and _normalize_for_similarity(repaired_script)
                    == _normalize_for_similarity(repaired_rewrites[index]["script"])
                )
                if not repaired_script or unsupported_flag:
                    repair_failed_indexes.append(index)
                elif no_progress:
                    repair_no_progress_indexes.append(index)
                repaired_rewrites[index] = {
                    **repaired_rewrites[index],
                    "script": repaired_script or repaired_rewrites[index]["script"],
                    "used_source_fact_ids": list(dict.fromkeys(repaired_ids)),
                    "provenance": (
                        "source_constrained_repair"
                        if repaired_script
                        else repaired_rewrites[index].get("provenance", "fact_review")
                    ),
                }
                repair_diagnostics.append(
                    {
                        "index": index,
                        "outcome": (
                            "invalid_repair"
                            if index in repair_failed_indexes
                            else "no_progress"
                            if no_progress
                            else "repaired"
                        ),
                        "before_chars": normalized_lengths[index],
                        "after_chars": _cjk_len(repaired_rewrites[index]["script"]),
                        "unused_source_fact_ids": [
                            fact_id
                            for fact_id in source_fact_ledger["fact_ids"]
                            if fact_id not in used_source_fact_ids[index]
                        ],
                        "used_source_fact_ids": repaired_rewrites[index]["used_source_fact_ids"],
                        "replacements": response.get("replacements") if isinstance(response.get("replacements"), list) else [],
                        "unsupported_spans": remaining_spans,
                        "elapsed_ms": elapsed_ms,
                    }
                )
            result = {**result, "rewrites": repaired_rewrites}
            normalized_lengths = [_cjk_len(item.get("script", "")) for item in result["rewrites"]]
            hard_violations_after = [
                unsupported_hard_facts(raw_script, rewrite["script"])
                for rewrite in result["rewrites"]
            ]
            verified_fact_coverage = [
                map_source_fact_coverage(
                    source_fact_ledger,
                    rewrite["script"],
                    claimed_fact_ids=list(rewrite.get("used_source_fact_ids") or []),
                )
                for rewrite in result["rewrites"]
            ]
            stage_timings.append(
                {
                    "stage": "source_constrained_repair",
                    "elapsed_ms": round((time.perf_counter() - repair_started) * 1000),
                    "variant_elapsed_ms": variant_elapsed_ms,
                    "parallel": True,
                    "requested_indexes": repair_indexes,
                }
            )
            length_repair_rounds.append(
                {
                    "round": len(length_repair_rounds),
                    "stage": "source_constrained_repair",
                    "requested_indexes": repair_indexes,
                    "actual_chars": list(normalized_lengths),
                }
            )
            fact_fidelity_diagnostic.update(
                {
                    "hard_violations_after": hard_violations_after,
                    "source_constrained_repairs": repair_diagnostics,
                    "repair_failed_indexes": repair_failed_indexes,
                    "repair_no_progress_indexes": repair_no_progress_indexes,
                    "unsupported_remaining": [
                        index
                        for index in unsupported_remaining
                        if index in repair_failed_indexes
                    ],
                    "unsupported_spans": [
                        spans if index in repair_failed_indexes else []
                        for index, spans in enumerate(unsupported_spans)
                    ],
                    "used_source_fact_ids": [
                        list(rewrite.get("used_source_fact_ids") or [])
                        for rewrite in result["rewrites"]
                    ],
                    "verified_fact_coverage": verified_fact_coverage,
                }
            )

        final_reconstruction_indexes = [
            index
            for index, length in enumerate(normalized_lengths)
            if (
                length < minimum_rewrite_chars
                or length > maximum_chars
                or index in repair_no_progress_indexes
            )
        ]
        if primary_model_rewrite_succeeded:
            final_reconstruction_indexes = [
                index for index in final_reconstruction_indexes if index != primary_index
            ]
        else:
            final_reconstruction_indexes = []
        final_reconstruction_diagnostics: list[dict[str, Any]] = []
        if final_reconstruction_indexes:
            async def reconstruct_variant(index: int) -> tuple[int, dict[str, Any], int]:
                nonlocal active_initial_calls, maximum_initial_concurrency
                reconstruction_started = time.perf_counter()
                rewrite = result["rewrites"][index]
                async with initial_semaphore:
                    call_number = await llm_budget.reserve()
                    async with concurrency_lock:
                        active_initial_calls += 1
                        maximum_initial_concurrency = max(
                            maximum_initial_concurrency,
                            active_initial_calls,
                        )
                    try:
                        response = await LLMProvider().generate_json(
                            system=(
                                "你是来源约束的完整口播重构编辑。只输出合法 JSON。"
                                "原始转写和来源事实账本是唯一事实来源；这是完整替换稿，不是自由扩写或追加段落。"
                            ),
                            payload={
                                "corrected_transcript": raw_script,
                                "source_fact_ledger": source_fact_ledger,
                                "current_version": {
                                    "index": index,
                                    "title": rewrite["title"],
                                    "script": rewrite["script"],
                                    "current_chars": normalized_lengths[index],
                                    "angle": variant_requirements[index],
                                },
                                "length_target": {
                                    "minimum_chars": minimum_rewrite_chars,
                                    "center_chars": target_center_chars,
                                    "maximum_chars": maximum_chars,
                                    "unit": "cjk_chars",
                                },
                                "requirements": [
                                    "重新组织为一篇完整替换稿，不得返回补充段落，不得沿用长度不足的原稿",
                                    "只能重组、解释和连接 corrected_transcript 与 source_fact_ledger 中已有的来源事实",
                                    "禁止新增数字、百分比、日期、周期、数量、机构、公司、人物、案例、指标或确定性因果",
                                    f"完整正文严格保持在 {minimum_rewrite_chars}–{maximum_chars} CJK，瞄准约 {target_center_chars}",
                                    "保持 current_version.angle；B保持用户痛点，C保持信息分析与内容表达角度",
                                    "句尾完整，不机械重复来源句，不重复 CTA",
                                    "used_source_fact_ids 仅作诊断提示，不要求列满；不得为了列满ID虚构正文",
                                    "unsupported_spans 必须如实列出仍无来源支持的片段，没有则为空数组",
                                ],
                                "schema": {
                                    "reconstructed_script": "基于来源事实重新组织的完整替换口播稿",
                                    "used_source_fact_ids": ["正文实际使用的来源事实ID，仅作提示"],
                                    "unsupported_spans": [],
                                    "unsupported_remaining": False,
                                },
                            },
                            max_tokens=MAX_SUPPLEMENT_RESPONSE_TOKENS,
                            attempt_label=f"final_source_reconstruction_{index}_call_{call_number}",
                            max_transport_attempts=1,
                            allow_format_repair=False,
                            thinking_mode="disabled",
                        )
                    finally:
                        async with concurrency_lock:
                            active_initial_calls -= 1
                return (
                    index,
                    response,
                    round((time.perf_counter() - reconstruction_started) * 1000),
                )

            reconstruction_started = time.perf_counter()
            reconstruction_results = await asyncio.gather(
                *(reconstruct_variant(index) for index in final_reconstruction_indexes),
                return_exceptions=True,
            )
            reconstructed_rewrites = list(result["rewrites"])
            reconstruction_failed_indexes: list[int] = []
            variant_elapsed_ms: list[int | None] = []
            for expected_index, value in zip(
                final_reconstruction_indexes,
                reconstruction_results,
                strict=True,
            ):
                response: dict[str, Any] = {}
                elapsed_ms: int | None = None
                provider_error = isinstance(value, BaseException)
                if provider_error:
                    index = expected_index
                else:
                    index, response, elapsed_ms = value
                variant_elapsed_ms.append(elapsed_ms)
                claimed_ids = [
                    str(item)
                    for item in (response.get("used_source_fact_ids") or [])
                    if str(item) in source_fact_ids
                ]
                reconstructed_script = smooth_spoken_script(
                    str(response.get("reconstructed_script") or "")
                )
                reconstructed_script = _trim_to_sentence_boundary(
                    reconstructed_script,
                    minimum_chars=minimum_rewrite_chars,
                    maximum_chars=maximum_chars,
                )
                response_spans = response.get("unsupported_spans")
                response_spans = (
                    [
                        item
                        for item in response_spans
                        if isinstance(item, dict) and str(item.get("span") or "").strip()
                    ]
                    if isinstance(response_spans, list)
                    else [{"span": "", "reason": "missing_unsupported_spans"}]
                )
                reconstructed_mapping = map_source_fact_coverage(
                    source_fact_ledger,
                    reconstructed_script,
                    claimed_fact_ids=claimed_ids,
                )
                reconstructed_length = _cjk_len(reconstructed_script)
                reconstruction_valid = (
                    not provider_error
                    and minimum_rewrite_chars <= reconstructed_length <= maximum_chars
                    and response.get("unsupported_remaining") is False
                    and not response_spans
                    and not reconstructed_mapping["unsupported_spans"]
                    and not _repeated_sentence_spans(reconstructed_script)
                    and reconstructed_script.rstrip().endswith(tuple("。！？!?"))
                )
                outcome = "reconstructed"
                applied_script = reconstructed_script
                applied_mapping = reconstructed_mapping
                if not reconstruction_valid:
                    outcome = "failed"
                    reconstruction_failed_indexes.append(index)
                    applied_script = reconstructed_rewrites[index]["script"]
                    applied_mapping = map_source_fact_coverage(
                        source_fact_ledger,
                        applied_script,
                        claimed_fact_ids=list(
                            reconstructed_rewrites[index].get("used_source_fact_ids") or []
                        ),
                    )

                reconstructed_rewrites[index] = {
                    **reconstructed_rewrites[index],
                    "script": applied_script,
                    "used_source_fact_ids": list(
                        applied_mapping["directly_supported_fact_ids"]
                    ),
                    "provenance": (
                        "final_source_reconstruction"
                        if outcome == "reconstructed"
                        else reconstructed_rewrites[index].get("provenance", "source_constrained_repair")
                    ),
                }
                final_reconstruction_diagnostics.append(
                    {
                        "index": index,
                        "outcome": outcome,
                        "before_chars": normalized_lengths[index],
                        "after_chars": _cjk_len(applied_script),
                        "model_claimed_fact_ids": list(dict.fromkeys(claimed_ids)),
                        "directly_supported_fact_ids": applied_mapping[
                            "directly_supported_fact_ids"
                        ],
                        "uncertain_fact_ids": applied_mapping["uncertain_fact_ids"],
                        "unsupported_spans": applied_mapping["unsupported_spans"],
                        "provider_error": (
                            type(value).__name__ if provider_error else ""
                        ),
                        "elapsed_ms": elapsed_ms,
                    }
                )

            result = {**result, "rewrites": reconstructed_rewrites}
            normalized_lengths = [
                _cjk_len(item.get("script", "")) for item in result["rewrites"]
            ]
            hard_violations_after = [
                unsupported_hard_facts(raw_script, rewrite["script"])
                for rewrite in result["rewrites"]
            ]
            verified_fact_coverage = [
                map_source_fact_coverage(
                    source_fact_ledger,
                    rewrite["script"],
                    claimed_fact_ids=list(rewrite.get("used_source_fact_ids") or []),
                )
                for rewrite in result["rewrites"]
            ]
            repair_failed_indexes = [
                index
                for index in repair_failed_indexes
                if index not in final_reconstruction_indexes
                or index in reconstruction_failed_indexes
            ]
            stage_timings.append(
                {
                    "stage": "final_source_reconstruction",
                    "elapsed_ms": round(
                        (time.perf_counter() - reconstruction_started) * 1000
                    ),
                    "variant_elapsed_ms": variant_elapsed_ms,
                    "parallel": True,
                    "requested_indexes": final_reconstruction_indexes,
                }
            )
            fact_fidelity_diagnostic.update(
                {
                    "hard_violations_after": hard_violations_after,
                    "verified_fact_coverage": verified_fact_coverage,
                    "final_source_reconstruction": final_reconstruction_diagnostics,
                    "repair_failed_indexes": repair_failed_indexes,
                    "unsupported_remaining": [
                        index
                        for index in fact_fidelity_diagnostic.get(
                            "unsupported_remaining",
                            [],
                        )
                        if index in reconstruction_failed_indexes
                    ],
                    "unsupported_spans": [
                        spans if index in reconstruction_failed_indexes else []
                        for index, spans in enumerate(
                            fact_fidelity_diagnostic.get(
                                "unsupported_spans",
                                [[], [], []],
                            )
                        )
                    ],
                    "final_reconstruction_failed_indexes": list(
                        dict.fromkeys(reconstruction_failed_indexes)
                    ),
                }
            )
            llm_call_count = llm_budget.used_calls
            logger.warning(
                "viral_final_source_reconstruction request_id=%s requested_indexes=%s "
                "outcomes=%s actual_chars=%s llm_call_count=%s maximum_llm_calls=%s",
                current_request_id(),
                final_reconstruction_indexes,
                [item["outcome"] for item in final_reconstruction_diagnostics],
                normalized_lengths,
                llm_call_count,
                MAX_SOURCE_CONSTRAINED_LLM_CALLS,
            )

    source_fact_coverage: list[dict[str, Any]] = []
    requested_count = FINAL_REWRITE_LIMIT
    filtered_duplicate_count = 0
    filtered_invalid_count = 0
    model_invalid_count = 0
    fallback_generated_count = 0
    degraded_to_scaffold = False
    scaffold_polish_diagnostic: dict[str, Any] = {"attempted": False}
    candidate_failure_diagnostics: list[dict[str, Any]] = []
    similar_pairs: list[dict[str, Any]] = []
    union_source_fact_coverage: dict[str, Any] = {}
    if source_scope == "full_content":
        def validate_candidate(index: int, rewrite: dict[str, Any]) -> dict[str, Any]:
            return _candidate_quality_snapshot(
                index=index,
                rewrite=rewrite,
                raw_script=raw_script,
                source_fact_ledger=source_fact_ledger,
                minimum_chars=minimum_rewrite_chars,
                maximum_chars=maximum_chars,
                minimum_fact_coverage_count=minimum_fact_coverage_count,
            )

        candidate_diagnostics = [
            validate_candidate(index, rewrite)
            for index, rewrite in enumerate(result["rewrites"])
        ]
        candidate_failure_diagnostics = [
            _candidate_diagnostic_record(item) for item in candidate_diagnostics
        ]
        logger.warning(
            "viral_final_candidate_validation request_id=%s candidates=%s",
            current_request_id(),
            candidate_failure_diagnostics,
        )
        valid_candidates = [
            item
            for item in candidate_diagnostics
            if item["valid"]
            and item["rewrite"].get("provenance")
            not in {"deterministic_scaffold", "scaffold_polished_by_model"}
        ]
        model_invalid_count = sum(
            1
            for item in candidate_diagnostics
            if not item["valid"]
            or item["rewrite"].get("provenance")
            in {"deterministic_scaffold", "scaffold_polished_by_model"}
        )

        if not valid_candidates:
            scaffold = _source_backed_scaffold(
                source_fact_ledger=source_fact_ledger,
                index=0,
                minimum_chars=minimum_rewrite_chars,
                target_center_chars=target_center_chars,
                maximum_chars=maximum_chars,
            )
            scaffold_candidate = validate_candidate(
                0,
                {
                    "title": "来源保底整理稿",
                    "script": scaffold,
                    "used_source_fact_ids": [],
                    "provenance": "deterministic_scaffold",
                },
            )
            candidate_failure_diagnostics.append(
                _candidate_diagnostic_record(scaffold_candidate)
            )
            if scaffold_candidate["valid"]:
                fallback_generated_count = 1
                degraded_to_scaffold = True
                polished_candidate: dict[str, Any] | None = None
                if llm_budget.used_calls < MAX_SOURCE_CONSTRAINED_LLM_CALLS:
                    polish_attempts: list[dict[str, Any]] = []
                    scaffold_polish_diagnostic = {
                        "attempted": True,
                        "attempts": polish_attempts,
                    }
                    previous_polish_script = ""
                    previous_failure: dict[str, Any] | None = None
                    for polish_attempt in range(1, 3):
                        if polish_attempt == 2 and previous_failure is None:
                            break
                        if llm_budget.used_calls >= MAX_SOURCE_CONSTRAINED_LLM_CALLS:
                            break
                        polish_started = time.perf_counter()
                        try:
                            call_number = await llm_budget.reserve()
                            polish_payload: dict[str, Any] = {
                                "scaffold_polish": True,
                                "source_fact_ledger": source_fact_ledger,
                                "scaffold": scaffold,
                                "length_target": {
                                    "minimum_chars": minimum_rewrite_chars,
                                    "target_chars": (
                                        min(maximum_chars, 780)
                                        if maximum_chars >= 720
                                        else target_center_chars
                                    ),
                                    "maximum_chars": maximum_chars,
                                    "unit": "cjk_chars",
                                },
                                "requirements": [
                                    "保持scaffold表达的全部事实，不得新增、删除或改变事实",
                                    f"正文保持在 {minimum_rewrite_chars}–{maximum_chars} CJK",
                                    "改为自然连续的知识口播，合并碎片句并保留必要停顿",
                                    "禁止逐行ASR样式，使用少量自然段",
                                    "禁止投资确定性承诺，不得新增数字、机构、日期、周期、案例、指标或因果结论",
                                    "返回完整正文并以完整句结束",
                                    "used_source_fact_ids只列正文实际表达的事实ID",
                                ],
                                "schema": {
                                    "title": "来源事实AI润色稿标题",
                                    "script": "等事实自然口播正文",
                                    "used_source_fact_ids": ["正文实际使用的来源事实ID"],
                                },
                            }
                            if polish_attempt == 2:
                                polish_payload.update(
                                    {
                                        "scaffold_polish_retry": True,
                                        "previous_polish_script": previous_polish_script,
                                        "previous_failure": previous_failure,
                                        "retry_requirement": (
                                            "只修复previous_failure列出的精确问题；仍返回完整替换稿，禁止追加补丁。"
                                        ),
                                    }
                                )
                            polish_response = await LLMProvider().generate_json(
                                system=(
                                    "你是来源事实等价口语润色编辑。scaffold和事实账本是唯一来源。"
                                    "不得新增、删除或改变事实。只输出最小合法 JSON。"
                                ),
                                payload=polish_payload,
                                max_tokens=MAX_SUPPLEMENT_RESPONSE_TOKENS,
                                attempt_label=(
                                    f"scaffold_polish_call_{call_number}"
                                    if polish_attempt == 1
                                    else f"scaffold_polish_retry_call_{call_number}"
                                ),
                                max_transport_attempts=1,
                                allow_format_repair=False,
                                thinking_mode="disabled",
                            )
                            polished_script = _natural_paragraphs(
                                smooth_spoken_script(
                                    str(polish_response.get("script") or "")
                                )
                            )
                            if _cjk_len(polished_script) > maximum_chars:
                                polished_script = _trim_to_sentence_boundary(
                                    polished_script,
                                    minimum_chars=minimum_rewrite_chars,
                                    maximum_chars=maximum_chars,
                                )
                            polished_candidate = validate_candidate(
                                0,
                                {
                                    "title": str(
                                        polish_response.get("title")
                                        or "来源事实AI润色稿"
                                    ),
                                    "script": polished_script,
                                    "used_source_fact_ids": [
                                        str(item)
                                        for item in (
                                            polish_response.get("used_source_fact_ids") or []
                                        )
                                        if str(item) in source_fact_ids
                                    ],
                                    "provenance": "scaffold_polished_by_model",
                                },
                            )
                            polished_record = _candidate_diagnostic_record(
                                polished_candidate
                            )
                            candidate_failure_diagnostics.append(polished_record)
                            attempt_record = {
                                "attempt": polish_attempt,
                                "outcome": (
                                    "succeeded"
                                    if polished_candidate["valid"]
                                    else "invalid"
                                ),
                                "candidate_diagnostic": polished_record,
                                "elapsed_ms": round(
                                    (time.perf_counter() - polish_started) * 1000
                                ),
                            }
                            polish_attempts.append(attempt_record)
                            scaffold_polish_diagnostic.update(
                                {
                                    "outcome": attempt_record["outcome"],
                                    "actual_chars": polished_candidate["actual_chars"],
                                    "reasons": polished_candidate["exact_failure_reasons"],
                                }
                            )
                            if polished_candidate["valid"]:
                                break
                            previous_polish_script = polished_script
                            previous_failure = polished_record
                        except (LLMProviderError, _LLMCallBudgetExceeded) as error:
                            polish_attempts.append(
                                {
                                    "attempt": polish_attempt,
                                    "outcome": "provider_error",
                                    "error_type": type(error).__name__,
                                    "elapsed_ms": round(
                                        (time.perf_counter() - polish_started) * 1000
                                    ),
                                }
                            )
                            scaffold_polish_diagnostic.update(polish_attempts[-1])
                            break
                        except Exception as error:
                            polish_attempts.append(
                                {
                                    "attempt": polish_attempt,
                                    "outcome": "invalid_response",
                                    "error_type": type(error).__name__,
                                    "elapsed_ms": round(
                                        (time.perf_counter() - polish_started) * 1000
                                    ),
                                }
                            )
                            scaffold_polish_diagnostic.update(polish_attempts[-1])
                            break
                valid_candidates = [
                    polished_candidate
                    if polished_candidate is not None and polished_candidate["valid"]
                    else scaffold_candidate
                ]

        if not valid_candidates:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "analysis_fact_fidelity_failed",
                    "stage": "final_variant_validation",
                    "message": "所有候选版本及主稿保底均未通过长度与事实校验。",
                    "retryable": False,
                    "actual_chars": normalized_lengths,
                    "candidate_diagnostics": candidate_failure_diagnostics,
                    "minimum_source_fact_coverage_count": minimum_fact_coverage_count,
                    "fact_fidelity": fact_fidelity_diagnostic,
                    "stage_timings": stage_timings,
                    "llm_call_count": llm_call_count,
                    "maximum_llm_calls": MAX_SOURCE_CONSTRAINED_LLM_CALLS,
                },
            )

        retained = [valid_candidates[0]]
        primary_script = retained[0]["rewrite"]["script"]
        for candidate in valid_candidates[1:]:
            duplicate_similarity = max(
                rewrite_similarity(candidate["rewrite"]["script"], item["rewrite"]["script"])
                for item in retained
            )
            if duplicate_similarity <= MAX_VARIANT_SIMILARITY:
                retained.append(candidate)
                continue

            diversified: dict[str, Any] | None = None
            try:
                call_number = await llm_budget.reserve()
                diversification = await LLMProvider().generate_json(
                    system=(
                        "你是来源约束的差异化编辑。只重写当前重复版本；原始转写和来源事实账本"
                        "是唯一事实来源。不得改写主版本，不得新增事实。只输出合法 JSON。"
                    ),
                    payload={
                        "corrected_transcript": raw_script,
                        "source_fact_ledger": source_fact_ledger,
                        "primary_script": primary_script,
                        "current_duplicate_variant": candidate["rewrite"],
                        "variant_angle": variant_requirements[candidate["index"]],
                        "preferred_source_facts": _variant_fact_subset(
                            source_fact_ledger,
                            candidate["index"],
                        ),
                        "forbidden_openings": [
                            str(item["rewrite"]["script"])[:80]
                            for item in retained
                        ],
                        "length_target": {
                            "minimum_chars": minimum_rewrite_chars,
                            "target_center_chars": target_center_chars,
                            "maximum_chars": maximum_chars,
                        },
                        "requirements": [
                            "改变叙事结构、受众问题和信息顺序，不得仅换标题、段落或连接词",
                            "优先使用本角度 preferred_source_facts；不要求覆盖全部来源事实",
                            f"至少覆盖 {minimum_fact_coverage_count} 条可直接支持的来源事实",
                            "不得新增数字、机构、时间、案例、指标、结论或确定性因果",
                            f"正文必须为 {minimum_rewrite_chars}–{maximum_chars} CJK，句尾完整且内部不重复",
                            "used_source_fact_ids 只列正文实际表达的事实 ID",
                        ],
                        "schema": {
                            "diversified_script": "差异化后的完整口播正文",
                            "used_source_fact_ids": ["正文实际表达的来源事实 ID"],
                        },
                    },
                    max_tokens=MAX_SUPPLEMENT_RESPONSE_TOKENS,
                    attempt_label=f"targeted_diversification_{candidate['index']}_call_{call_number}",
                    max_transport_attempts=1,
                    allow_format_repair=False,
                    thinking_mode="disabled",
                )
                diversified_script = smooth_spoken_script(
                    str(diversification.get("diversified_script") or "")
                )
                diversified_candidate = validate_candidate(
                    candidate["index"],
                    {
                        **candidate["rewrite"],
                        "script": diversified_script,
                        "used_source_fact_ids": list(
                            dict.fromkeys(diversification.get("used_source_fact_ids") or [])
                        ),
                        "provenance": "targeted_diversification",
                    },
                )
                if diversified_candidate["valid"] and all(
                    rewrite_similarity(
                        diversified_candidate["rewrite"]["script"],
                        item["rewrite"]["script"],
                    )
                    <= MAX_VARIANT_SIMILARITY
                    for item in retained
                ):
                    diversified = diversified_candidate
            except (LLMProviderError, _LLMCallBudgetExceeded):
                diversified = None
            except Exception as error:
                logger.warning(
                    "viral_targeted_diversification request_id=%s index=%s outcome=failed error_type=%s",
                    current_request_id(),
                    candidate["index"],
                    type(error).__name__,
                )
                diversified = None

            if diversified is not None:
                retained.append(diversified)
            else:
                filtered_duplicate_count += 1
                for diagnostic in candidate_failure_diagnostics:
                    if diagnostic["index"] == candidate["index"]:
                        diagnostic["similarity_failure"] = True
                        if "similarity" not in diagnostic["exact_failure_reasons"]:
                            diagnostic["exact_failure_reasons"].append("similarity")
                        diagnostic["valid"] = False
                        break
                similar_pairs.append(
                    {
                        "left": retained[0]["index"],
                        "right": candidate["index"],
                        "similarity": round(duplicate_similarity, 4),
                    }
                )

        logger.warning(
            "viral_final_candidate_outcomes request_id=%s candidates=%s",
            current_request_id(),
            candidate_failure_diagnostics,
        )
        primary_script = retained[0]["rewrite"]["script"]
        finalized_rewrites = []
        source_fact_coverage = []
        union_fact_ids: list[str] = []
        for output_index, candidate in enumerate(retained):
            coverage = {**candidate["coverage"], "index": output_index}
            source_fact_coverage.append(coverage)
            union_fact_ids.extend(coverage["directly_supported_fact_ids"])
            rewrite = candidate["rewrite"]
            finalized_rewrites.append(
                {
                    **rewrite,
                    "angle": variant_requirements[candidate["index"]],
                    "actual_chars": candidate["actual_chars"],
                    "source_fact_coverage": coverage,
                    "provenance": rewrite.get("provenance", "independent_initial"),
                    "similarity_to_primary": (
                        0.0
                        if output_index == 0
                        else round(rewrite_similarity(primary_script, rewrite["script"]), 4)
                    ),
                    "fact_fidelity": {
                        "hard_violations": candidate["hard_violations"],
                        "unsupported_spans": coverage["unsupported_spans"],
                        "valid": True,
                    },
                }
            )
        result = {**result, "rewrites": finalized_rewrites}
        normalized_lengths = [item["actual_chars"] for item in finalized_rewrites]
        union_ids = list(dict.fromkeys(union_fact_ids))
        union_source_fact_coverage = {
            "directly_supported_fact_ids": union_ids,
            "used_count": len(union_ids),
            "total_count": source_fact_ledger["fact_count"],
            "coverage_rate": (
                round(len(union_ids) / source_fact_ledger["fact_count"], 4)
                if source_fact_ledger["fact_count"]
                else 0.0
            ),
        }
        llm_call_count = llm_budget.used_calls

    generated_count = len(result["rewrites"])
    filtered_invalid_count = max(
        0,
        requested_count - generated_count - filtered_duplicate_count,
    )
    final_provenance = (
        str(result["rewrites"][0].get("provenance") or "")
        if result["rewrites"]
        else ""
    )
    model_rewrite_succeeded = bool(
        result["rewrites"]
        and final_provenance
        not in {"deterministic_scaffold", "scaffold_polished_by_model"}
    )
    degraded = generated_count < requested_count
    degradation_reason = ""
    if final_provenance == "deterministic_scaffold":
        degradation_reason = (
            "AI改写版本未通过质量校验，当前展示来源保底整理稿。"
            "内容基于原转写，事实安全，但改写程度有限。"
        )
    elif final_provenance == "scaffold_polished_by_model":
        degradation_reason = "独立改写版本未通过校验，当前展示基于来源事实的AI润色稿。"
    elif degraded:
        if filtered_duplicate_count and generated_count == 1:
            degradation_reason = "其他角度与主稿过于相似，已过滤"
        elif filtered_duplicate_count:
            degradation_reason = f"已过滤{filtered_duplicate_count}条高度相似版本"
        else:
            degradation_reason = f"已过滤{filtered_invalid_count}条未通过质量校验的版本"

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

    return {
        **result,
        "generated_count": generated_count,
        "requested_count": requested_count,
        "filtered_duplicate_count": filtered_duplicate_count,
        "filtered_invalid_count": filtered_invalid_count,
        "model_invalid_count": model_invalid_count,
        "fallback_generated_count": fallback_generated_count,
        "degraded_to_scaffold": degraded_to_scaffold,
        "provenance": final_provenance,
        "model_rewrite_succeeded": model_rewrite_succeeded,
        "degraded": degraded,
        "degradation_reason": degradation_reason,
        "variants": result["rewrites"],
        "union_source_fact_coverage": union_source_fact_coverage,
        "quota": {**quota, "used": quota["used"] + 1},
        "diagnostic": {
            "actual_chars": normalized_lengths,
            "target_chars": minimum_rewrite_chars,
            "target_center_chars": target_center_chars,
            "maximum_chars": maximum_chars,
            "length_unit": "cjk_chars",
            "length_repair_rounds": length_repair_rounds,
            "fact_fidelity": fact_fidelity_diagnostic,
            "source_fact_coverage": source_fact_coverage,
            "union_source_fact_coverage": union_source_fact_coverage,
            "similar_pairs": similar_pairs,
            "generated_count": generated_count,
            "requested_count": requested_count,
            "filtered_duplicate_count": filtered_duplicate_count,
            "filtered_invalid_count": filtered_invalid_count,
            "model_invalid_count": model_invalid_count,
            "fallback_generated_count": fallback_generated_count,
            "degraded_to_scaffold": degraded_to_scaffold,
            "provenance": final_provenance,
            "model_rewrite_succeeded": model_rewrite_succeeded,
            "primary_selection": primary_selection_diagnostic,
            "scaffold_polish": scaffold_polish_diagnostic,
            "candidate_failure_diagnostics": candidate_failure_diagnostics,
            "stage_timings": stage_timings,
            "llm_call_count": llm_call_count,
            "maximum_llm_calls": MAX_SOURCE_CONSTRAINED_LLM_CALLS,
            "version_states": version_states,
            "initial_concurrency_limit": SOURCE_INITIAL_CONCURRENCY,
            "maximum_observed_concurrency": maximum_initial_concurrency,
            **length_target.diagnostics(),
        },
        "diagnostics": {
            "prompt_input_chars": prompt_input_chars + len(analysis_input),
            "hierarchical_chunk_count": summary_chunk_count,
            "output_chars": sum(len(str(value)) for value in result.values()),
            "rewrite_length_requested": rewrite_length,
            "rewrite_length_effective": length_target.length_mode,
            "rewrite_target_chars": minimum_rewrite_chars,
            "rewrite_target_center_chars": target_center_chars,
            "rewrite_maximum_chars": maximum_chars,
            "rewrite_actual_chars": normalized_lengths,
            "length_repair_rounds": length_repair_rounds,
            "fact_fidelity": fact_fidelity_diagnostic,
            "source_fact_coverage": source_fact_coverage,
            "union_source_fact_coverage": union_source_fact_coverage,
            "similar_pairs": similar_pairs,
            "generated_count": generated_count,
            "requested_count": requested_count,
            "filtered_duplicate_count": filtered_duplicate_count,
            "filtered_invalid_count": filtered_invalid_count,
            "model_invalid_count": model_invalid_count,
            "fallback_generated_count": fallback_generated_count,
            "degraded_to_scaffold": degraded_to_scaffold,
            "provenance": final_provenance,
            "model_rewrite_succeeded": model_rewrite_succeeded,
            "primary_selection": primary_selection_diagnostic,
            "scaffold_polish": scaffold_polish_diagnostic,
            "candidate_failure_diagnostics": candidate_failure_diagnostics,
            "stage_timings": stage_timings,
            "llm_call_count": llm_call_count,
            "maximum_llm_calls": MAX_SOURCE_CONSTRAINED_LLM_CALLS,
            "version_states": version_states,
            "initial_concurrency_limit": SOURCE_INITIAL_CONCURRENCY,
            "maximum_observed_concurrency": maximum_initial_concurrency,
            **length_target.diagnostics(),
        },
    }
