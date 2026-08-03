from __future__ import annotations

import re
import unicodedata
from typing import Any


ARABIC_FACT_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:\d{4}[年./-]\d{1,2}(?:[月./-]\d{1,2}日?)?|\d+(?:\.\d+)?(?:%|％)?)"
)
CHINESE_TIME_QUANTITY_RE = re.compile(
    r"(?:过去|未来|最近|近|连续|每隔|每|前)?"
    r"(?:半|[零〇一二两三四五六七八九十百千万]+)"
    r"(?:个)?(?:交易日|工作日|小时|分钟|秒|天|日|周|月份|个月|月|季度|季|年度|年|期)"
    r"(?:内|后|前|以来|以上|以下|左右)?"
)
RELATIVE_TIME_RE = re.compile(r"(?:每月|每季度|每年|半年后|前十大)")
LATIN_ACRONYM_RE = re.compile(r"(?<![A-Za-z])[A-Z]{2,}(?![A-Za-z])")

FINANCE_DOMAIN_MARKERS = (
    "资本市场",
    "上市公司",
    "回购",
    "保险机构",
    "基金",
    "私募",
    "公募",
    "ETF",
    "中报",
    "产业链",
    "外资",
    "股价",
    "指数",
)

# These are concrete evidence types that models commonly invent when a source
# only contains a general observation. They remain allowed when the source
# itself contains the same term.
HIGH_RISK_FACT_TERMS = (
    "ROE",
    "净资产收益率",
    "前十大流通股东",
    "流通股东名单",
    "ETF份额",
    "目标价",
    "股价修复",
    "股价慢慢修复",
    "连续超预期",
    "一致上修",
    "多数上修",
    "环比",
    "同比",
    "毛利率",
    "净资产占比",
    "权益类资产占比",
    "季度资金运用报告",
    "低基数",
    "政府补贴",
    "一季报",
)

ORGANIZATION_RE = re.compile(
    r"[\u4e00-\u9fffA-Za-z·]{2,24}"
    r"(?:集团|公司|银行|证券|基金|保险|私募|公募|机构|交易所)"
)
UNSOURCED_GENERIC_ENTITY_RE = re.compile(r"某(?:集团|公司|银行|证券|基金|保险|私募|公募|机构|交易所)")
SOURCE_SENTENCE_RE = re.compile(r"[^。！？!?；;]+[。！？!?；;]?")

FACT_CATEGORY_RULES = (
    (
        "机构及表态",
        ("资本市场", "指数波动", "板块轮动", "参与者", "长期信心", "保险机构", "市场预期", "实体经济", "新兴产业", "机构表态"),
    ),
    (
        "回购及限定条件",
        ("上市公司", "增持", "回购", "总股本", "每股收益", "股东权益", "资金来源", "回购价格", "公司基本面", "现金流", "盈利能力"),
    ),
    (
        "自购与ETF",
        ("自购", "ETF申购", "私募", "公募", "长期资金", "指数产品", "风险偏好", "短期情绪"),
    ),
    (
        "中报和产业链",
        ("中报", "产业链", "半导体", "订单", "价格变化", "库存周期", "一次性收益", "沪深三百", "中证五百", "科创五十", "成分权重"),
    ),
    (
        "外资观点",
        ("外资", "花旗集团", "摩根士丹利", "估值框架", "客户期限"),
    ),
    (
        "风险边界",
        ("不能", "不是确定性", "更稳妥", "风险边界", "核对", "持续证据", "修正判断"),
    ),
)

FACT_CATEGORY_PREFIX = {
    "机构及表态": "INST",
    "回购及限定条件": "BUYBACK",
    "自购与ETF": "ETF",
    "中报和产业链": "CHAIN",
    "外资观点": "FOREIGN",
    "风险边界": "RISK",
    "其他来源事实": "SOURCE",
}

RISK_REQUIRED_MARKERS = (
    "不得",
    "不是确定性",
    "不意味着",
    "不等于",
    "不一定",
    "风险边界",
    "收益承诺",
    "买入信号",
)


def _normalized_token(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or ""))).lower()


def _arabic_to_chinese(value: str) -> str | None:
    if not value.isdigit():
        return None
    number = int(value)
    if number < 0 or number > 9999:
        return None
    digits = "零一二三四五六七八九"
    if number < 10:
        return digits[number]
    units = ((1000, "千"), (100, "百"), (10, "十"))
    result = ""
    remainder = number
    pending_zero = False
    for unit_value, unit_name in units:
        digit, remainder = divmod(remainder, unit_value)
        if digit:
            if pending_zero and result:
                result += "零"
            if not (unit_value == 10 and digit == 1 and not result):
                result += digits[digit]
            result += unit_name
            pending_zero = False
        elif result and remainder:
            pending_zero = True
    if remainder:
        if pending_zero and result:
            result += "零"
        result += digits[remainder]
    return result or "零"


def _token_supported(source_normalized: str, token: str) -> bool:
    normalized = _normalized_token(token)
    if normalized and normalized in source_normalized:
        return True
    numeric = re.fullmatch(r"\d+", normalized)
    if numeric:
        chinese = _arabic_to_chinese(numeric.group(0))
        return bool(chinese and chinese in source_normalized)
    return False


def _unique_matches(pattern: re.Pattern[str], value: str) -> list[str]:
    seen: set[str] = set()
    matches: list[str] = []
    for match in pattern.finditer(str(value or "")):
        token = match.group(0).strip()
        normalized = _normalized_token(token)
        if not token or normalized in seen:
            continue
        seen.add(normalized)
        matches.append(token)
    return matches


def extract_hard_fact_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for pattern in (ARABIC_FACT_TOKEN_RE, CHINESE_TIME_QUANTITY_RE, RELATIVE_TIME_RE, LATIN_ACRONYM_RE):
        for token in _unique_matches(pattern, value):
            normalized = _normalized_token(token)
            if normalized in seen:
                continue
            seen.add(normalized)
            tokens.append(token)
    return tokens


def unsupported_hard_facts(source: str, output: str) -> list[dict[str, str]]:
    source_normalized = _normalized_token(source)
    violations: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for token in extract_hard_fact_tokens(output):
        normalized = _normalized_token(token)
        if normalized and not _token_supported(source_normalized, token):
            key = ("number_or_time", normalized)
            if key not in seen:
                seen.add(key)
                violations.append({"category": "number_or_time", "value": token})

    for term in HIGH_RISK_FACT_TERMS:
        normalized = _normalized_token(term)
        if term in output and normalized not in source_normalized:
            key = ("indicator_or_specific_fact", normalized)
            if key not in seen:
                seen.add(key)
                violations.append({"category": "indicator_or_specific_fact", "value": term})

    for organization in _unique_matches(UNSOURCED_GENERIC_ENTITY_RE, output):
        normalized = _normalized_token(organization)
        if normalized in source_normalized:
            continue
        key = ("unsourced_entity", normalized)
        if key not in seen:
            seen.add(key)
            violations.append({"category": "unsourced_entity", "value": organization})
    return violations


def is_financial_source(source: str) -> bool:
    return sum(1 for marker in FINANCE_DOMAIN_MARKERS if marker in source) >= 3


def build_source_fact_ledger(
    source: str,
    normalized_sentences: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source_text = str(source or "")
    facts: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    evidence_items = normalized_sentences or [
        {"text": match.group(0).strip()} for match in SOURCE_SENTENCE_RE.finditer(source_text)
    ]
    seen_categories: set[str] = set()
    for evidence_item in evidence_items:
        evidence = str(evidence_item.get("text") or "").strip()
        if not evidence:
            continue
        category = "其他来源事实"
        best_score = 0
        for candidate, markers in FACT_CATEGORY_RULES:
            score = sum(1 for marker in markers if marker in evidence)
            if score > best_score:
                category = candidate
                best_score = score
        category_counts[category] = category_counts.get(category, 0) + 1
        fact_id = f"{FACT_CATEGORY_PREFIX[category]}-{category_counts[category]:02d}"
        hard_fact_tokens = extract_hard_fact_tokens(evidence)
        organizations = _unique_matches(ORGANIZATION_RE, evidence)
        if category == "风险边界" or any(marker in evidence for marker in RISK_REQUIRED_MARKERS):
            importance_tier = "risk_required"
            classification_reason = "risk_or_limitation_marker"
        elif category not in seen_categories:
            importance_tier = "core_required"
            classification_reason = "first_fact_in_category"
        else:
            importance_tier = "optional_support"
            classification_reason = "supporting_fact"
        seen_categories.add(category)
        fact = {
            "id": fact_id,
            "category": category,
            "claim": evidence.rstrip("。！？!?；;"),
            "evidence": evidence,
            "hard_fact_tokens": hard_fact_tokens,
            "organizations": organizations,
            "importance_tier": importance_tier,
            "classification_source": "deterministic_rule_v1",
            "classification_reason": classification_reason,
        }
        for key in (
            "source_segment_indexes",
            "source_segment_start",
            "source_segment_end",
            "start_seconds",
            "end_seconds",
        ):
            if key in evidence_item:
                fact[key] = evidence_item[key]
        facts.append(fact)
    tier_fact_ids = {
        tier: [item["id"] for item in facts if item["importance_tier"] == tier]
        for tier in ("core_required", "risk_required", "optional_support")
    }
    return {
        "facts": facts,
        "fact_ids": [item["id"] for item in facts],
        "fact_count": len(facts),
        "tier_fact_ids": tier_fact_ids,
        "tier_counts": {tier: len(ids) for tier, ids in tier_fact_ids.items()},
        "classification_source": "deterministic_rule_v1",
        "hard_fact_tokens": extract_hard_fact_tokens(source_text),
        "organizations": _unique_matches(ORGANIZATION_RE, source_text),
        "financial_indicators": [term for term in HIGH_RISK_FACT_TERMS if term in source_text],
        "rules": [
            "原始转写是唯一事实来源",
            "未出现在原始转写中的数字、时间范围、机构、公司事件、案例结果和指标不在白名单",
            "一般性解释必须明确写成判断方法或待核对条件，不能声称已经发生",
        ],
    }


def _character_ngrams(value: str, size: int) -> set[str]:
    normalized = _normalized_token(value)
    if len(normalized) < size:
        return {normalized} if normalized else set()
    return {
        normalized[index : index + size]
        for index in range(len(normalized) - size + 1)
    }


def map_source_fact_coverage(
    ledger: dict[str, Any],
    script: str,
    *,
    claimed_fact_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Map facts to visible script evidence without trusting model self-report."""
    script_normalized = _normalized_token(script)
    script_four_grams = _character_ngrams(script, 4)
    claimed = {
        str(item)
        for item in (claimed_fact_ids or [])
        if str(item) in set(ledger.get("fact_ids") or [])
    }
    directly_supported: list[str] = []
    uncertain: list[str] = []
    evidence: list[dict[str, Any]] = []

    for fact in ledger.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        fact_id = str(fact.get("id") or "")
        source_evidence = str(fact.get("evidence") or fact.get("claim") or "")
        evidence_normalized = _normalized_token(source_evidence)
        evidence_eight_grams = _character_ngrams(source_evidence, 8)
        matching_eight_grams = sorted(
            item for item in evidence_eight_grams if item and item in script_normalized
        )
        exact = bool(evidence_normalized and evidence_normalized in script_normalized)
        direct = exact or bool(matching_eight_grams)
        matching_four_grams = sorted(
            _character_ngrams(source_evidence, 4).intersection(script_four_grams)
        )
        if direct:
            directly_supported.append(fact_id)
        elif fact_id in claimed or matching_four_grams:
            uncertain.append(fact_id)
        evidence.append(
            {
                "fact_id": fact_id,
                "direct": direct,
                "exact_evidence": exact,
                "matching_evidence_fragments": matching_eight_grams[:3],
                "lexical_overlap_fragments": matching_four_grams[:3],
                "model_claimed": fact_id in claimed,
            }
        )

    tier_fact_ids = ledger.get("tier_fact_ids") or {}
    tier_coverage = {}
    directly_supported_set = set(directly_supported)
    for tier in ("core_required", "risk_required", "optional_support"):
        tier_ids = [str(item) for item in (tier_fact_ids.get(tier) or [])]
        covered_ids = [fact_id for fact_id in tier_ids if fact_id in directly_supported_set]
        tier_coverage[tier] = {
            "fact_ids": tier_ids,
            "covered_fact_ids": covered_ids,
            "missing_fact_ids": [fact_id for fact_id in tier_ids if fact_id not in directly_supported_set],
            "total": len(tier_ids),
            "covered": len(covered_ids),
        }
    return {
        "directly_supported_fact_ids": directly_supported,
        "uncertain_fact_ids": uncertain,
        "unsupported_spans": unsupported_hard_facts(
            "\n".join(
                str(item.get("evidence") or "")
                for item in (ledger.get("facts") or [])
                if isinstance(item, dict)
            ),
            script,
        ),
        "evidence": evidence,
        "tier_coverage": tier_coverage,
    }
