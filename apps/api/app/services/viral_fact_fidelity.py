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


def _normalized_token(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or ""))).lower()


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
        if normalized and normalized not in source_normalized:
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


def build_source_fact_ledger(source: str) -> dict[str, Any]:
    source_text = str(source or "")
    return {
        "hard_fact_tokens": extract_hard_fact_tokens(source_text),
        "organizations": _unique_matches(ORGANIZATION_RE, source_text),
        "financial_indicators": [term for term in HIGH_RISK_FACT_TERMS if term in source_text],
        "rules": [
            "原始转写是唯一事实来源",
            "未出现在原始转写中的数字、时间范围、机构、公司事件、案例结果和指标不在白名单",
            "一般性解释必须明确写成判断方法或待核对条件，不能声称已经发生",
        ],
    }
