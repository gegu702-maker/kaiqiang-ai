from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import logging
import re
from typing import Any

from app.services.asr_service import ASRSegment
from app.services.financial_terms import FINANCIAL_HOTWORDS, FINANCIAL_TERM_CORRECTIONS
from app.services.llm_provider import LLMProvider, LLMProviderError
from app.services.viral_diagnostics import current_request_id


logger = logging.getLogger(__name__)

ALLOWED_CHANGE_TYPES = {"homophone", "financial_term", "entity", "number_format", "punctuation"}
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")
CRITICAL_RESIDUAL_PATTERNS = ("�", "习近平", *[source for source, _target in FINANCIAL_TERM_CORRECTIONS])
TRUNCATED_END_RE = re.compile(r"(?:以及|并且|因为|所以|但是|而且|其中|对于|通过|随着|包括|如果|当)\s*$")
REPEATED_PHRASE_RE = re.compile(r"(.{4,16})(?:[，,。\s]*\1)+")


@dataclass
class CorrectionResult:
    corrected_transcript: str
    corrected_segments: list[ASRSegment]
    corrections: list[dict[str, Any]]
    review_segments: list[dict[str, Any]]
    quality_passed: bool
    provider: str = "financial_glossary+llm"


def _numbers(text: str) -> list[str]:
    return NUMBER_RE.findall(text)


def _safe_candidate(original: str, corrected: str, changes: Any) -> tuple[bool, str]:
    if not corrected or _numbers(original) != _numbers(corrected):
        return False, "数字内容发生变化"
    if abs(len(corrected) - len(original)) > max(12, int(len(original) * 0.35)):
        return False, "文本长度变化超过约束"
    if SequenceMatcher(None, original, corrected).ratio() < 0.55:
        return False, "文本变化幅度过大"
    if not isinstance(changes, list):
        return False, "缺少逐项修正记录"
    for change in changes:
        if not isinstance(change, dict):
            return False, "修正记录格式错误"
        before = str(change.get("from") or "")
        after = str(change.get("to") or "")
        change_type = str(change.get("type") or "")
        if not before or not after or before not in original or after not in corrected:
            return False, "修正记录与文本不一致"
        if change_type not in ALLOWED_CHANGE_TYPES:
            return False, "包含不允许的修正类型"
    return True, ""


def _apply_confirmed_terms(segments: list[ASRSegment]) -> tuple[list[ASRSegment], list[dict[str, Any]]]:
    corrected_segments: list[ASRSegment] = []
    corrections: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        text = segment.text
        for source, target in FINANCIAL_TERM_CORRECTIONS:
            if source not in text:
                continue
            count = text.count(source)
            text = text.replace(source, target)
            corrections.append(
                {
                    "segment_index": index,
                    "start": segment.start,
                    "end": segment.end,
                    "from": source,
                    "to": target,
                    "type": "financial_term",
                    "reason": "人工确认的金融ASR回归词条",
                    "count": count,
                    "source": "confirmed_glossary",
                }
            )
        corrected_segments.append(ASRSegment(start=segment.start, end=segment.end, text=text))
    return corrected_segments, corrections


async def correct_financial_transcript(segments: list[ASRSegment], language: str = "zh") -> CorrectionResult:
    glossary_segments, corrections = _apply_confirmed_terms(segments)
    review_segments: list[dict[str, Any]] = []
    normalized_segments: list[ASRSegment] = []
    for index, segment in enumerate(glossary_segments):
        raw_text = segments[index].text
        suggested = segment.text.replace("�", "")
        deduplicated = REPEATED_PHRASE_RE.sub(r"\1", suggested)
        if deduplicated != suggested:
            corrections.append(
                {
                    "segment_index": index,
                    "start": segment.start,
                    "end": segment.end,
                    "from": suggested,
                    "to": deduplicated,
                    "type": "punctuation",
                    "reason": "移除同一片段内连续重复的短语",
                    "count": 1,
                    "source": "structural_guard",
                }
            )
        suggested = deduplicated
        if "�" in raw_text:
            corrections.append(
                {
                    "segment_index": index,
                    "start": segment.start,
                    "end": segment.end,
                    "from": "�",
                    "to": "",
                    "type": "punctuation",
                    "reason": "移除无效Unicode替换字符，原音需人工复核",
                    "count": raw_text.count("�"),
                    "source": "unicode_guard",
                }
            )
            review_segments.append(
                {
                    "segment_index": index,
                    "start": segment.start,
                    "end": segment.end,
                    "original_text": raw_text,
                    "suggested_text": suggested,
                    "text": raw_text,
                    "reason": "原始ASR包含U+FFFD乱码，必须试听确认缺失内容",
                }
            )
        if TRUNCATED_END_RE.search(suggested):
            review_segments.append(
                {
                    "segment_index": index,
                    "start": segment.start,
                    "end": segment.end,
                    "original_text": raw_text,
                    "suggested_text": suggested,
                    "text": raw_text,
                    "reason": "句尾疑似截断，禁止自动补写",
                }
            )
        normalized_segments.append(ASRSegment(start=segment.start, end=segment.end, text=suggested))
    glossary_segments = normalized_segments
    payload = {
        "language": language,
        "domain": "金融市场与上市公司",
        "allowed_change_types": sorted(ALLOWED_CHANGE_TYPES),
        "financial_terms": FINANCIAL_HOTWORDS,
        "segments": [
            {"segment_index": index, "start": segment.start, "end": segment.end, "text": segment.text}
            for index, segment in enumerate(glossary_segments)
        ],
        "requirements": [
            "只修正同音词、金融术语、机构或指数实体、数字格式和标点",
            "不得新增原音频不存在的事实、数字、公司、人物或观点",
            "数字的值必须保持不变，只可调整合法格式",
            "没有把握的片段保持原文并标记 review_required=true",
            "只返回确实需要变化的片段；时间戳和 segment_index 不得变化",
        ],
        "schema": {
            "segments": [
                {
                    "segment_index": 0,
                    "original_text": "输入原文",
                    "corrected_text": "受约束校正稿",
                    "changes": [{"from": "错词", "to": "术语", "type": "financial_term", "reason": "同音金融术语"}],
                    "review_required": False,
                    "review_reason": "",
                }
            ]
        },
    }
    try:
        response = await LLMProvider().generate_json(
            system="你是中文金融音频转写校对员。严格受输入音频转写约束，只输出合法JSON，不做事实补写。",
            payload=payload,
            max_tokens=5000,
        )
    except Exception as error:
        code = error.code if isinstance(error, LLMProviderError) else type(error).__name__
        logger.warning(
            "viral_transcript_correction request_id=%s outcome=llm_failed code=%s",
            current_request_id(),
            code,
        )
        response = {"segments": []}
        review_segments.append({"segment_index": -1, "original_text": "", "suggested_text": "", "reason": f"AI校正服务失败：{code}"})

    by_index = {index: segment for index, segment in enumerate(glossary_segments)}
    for item in response.get("segments") or []:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("segment_index"))
        except (TypeError, ValueError):
            continue
        segment = by_index.get(index)
        if segment is None:
            continue
        original = segment.text
        supplied_original = str(item.get("original_text") or "")
        corrected = str(item.get("corrected_text") or "").strip()
        if supplied_original != original:
            review_segments.append({"segment_index": index, "start": segment.start, "end": segment.end, "original_text": segments[index].text, "suggested_text": original, "text": original, "reason": "AI返回的原文与对应片段不一致"})
            continue
        safe, reason = _safe_candidate(original, corrected, item.get("changes"))
        if item.get("review_required") or not safe:
            review_segments.append(
                {
                    "segment_index": index,
                    "start": segment.start,
                    "end": segment.end,
                    "text": original,
                    "original_text": segments[index].text,
                    "suggested_text": corrected if corrected and "�" not in corrected else original,
                    "reason": str(item.get("review_reason") or reason or "AI标记需人工复核"),
                }
            )
            continue
        if corrected == original:
            continue
        by_index[index] = ASRSegment(start=segment.start, end=segment.end, text=corrected)
        for change in item.get("changes") or []:
            corrections.append(
                {
                    "segment_index": index,
                    "start": segment.start,
                    "end": segment.end,
                    "from": str(change.get("from") or ""),
                    "to": str(change.get("to") or ""),
                    "type": str(change.get("type") or ""),
                    "reason": str(change.get("reason") or "AI受约束校正"),
                    "count": 1,
                    "source": "llm_constrained",
                }
            )

    corrected_segments = [by_index[index] for index in range(len(glossary_segments))]
    corrected_transcript = "\n".join(segment.text for segment in corrected_segments).strip()
    for index, segment in enumerate(corrected_segments):
        residuals = [pattern for pattern in CRITICAL_RESIDUAL_PATTERNS if pattern in segment.text]
        if residuals:
            review_segments.append(
                {
                    "segment_index": index,
                    "start": segment.start,
                    "end": segment.end,
                    "original_text": segments[index].text,
                    "suggested_text": segment.text.replace("�", ""),
                    "text": segments[index].text,
                    "reason": f"校正稿仍包含高风险异常词：{'、'.join(residuals)}",
                }
            )

    deduplicated_reviews: dict[int, dict[str, Any]] = {}
    global_reviews: list[dict[str, Any]] = []
    for item in review_segments:
        index = int(item.get("segment_index", -1))
        if index < 0:
            global_reviews.append(item)
            continue
        if index in deduplicated_reviews:
            deduplicated_reviews[index]["reason"] = f"{deduplicated_reviews[index]['reason']}；{item['reason']}"
        else:
            deduplicated_reviews[index] = item
    review_segments = [*deduplicated_reviews.values(), *global_reviews]

    logger.warning(
        "viral_transcript_correction request_id=%s outcome=completed raw_chars=%s corrected_chars=%s correction_count=%s review_segment_count=%s quality_passed=%s",
        current_request_id(),
        len("\n".join(segment.text for segment in segments)),
        len(corrected_transcript),
        sum(int(item.get("count") or 1) for item in corrections),
        len(review_segments),
        not review_segments,
    )
    return CorrectionResult(
        corrected_transcript=corrected_transcript,
        corrected_segments=corrected_segments,
        corrections=corrections,
        review_segments=review_segments,
        quality_passed=not review_segments,
    )
