from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import re
import unicodedata
from typing import Any, Iterable

from app.services.viral_fact_fidelity import (
    ARABIC_FACT_TOKEN_RE,
    CHINESE_TIME_QUANTITY_RE,
    FINANCE_DOMAIN_MARKERS,
    HIGH_RISK_FACT_TERMS,
    LATIN_ACRONYM_RE,
    ORGANIZATION_RE,
    RELATIVE_TIME_RE,
)


TERMINATORS = "。！？!?；;"
CLAUSE_PUNCTUATION = "，,、：:"
MIN_SENTENCE_CJK = 16
TARGET_SENTENCE_CJK = 34
MAX_SENTENCE_CJK = 54
PAUSE_BOUNDARY_SECONDS = 0.45
CONTINUATION_SUFFIXES = (
    "的",
    "和",
    "与",
    "以及",
    "并且",
    "因为",
    "所以",
    "但是",
    "而且",
    "其中",
    "对于",
    "通过",
    "随着",
    "包括",
    "如果",
    "当",
    "或",
)
PROTECTED_LITERAL_TERMS = tuple(
    dict.fromkeys((*FINANCE_DOMAIN_MARKERS, *HIGH_RISK_FACT_TERMS, "沪深三百", "中证五百", "科创五十"))
)


@dataclass(frozen=True)
class NormalizedSentence:
    text: str
    source_segment_indexes: list[int]
    start_seconds: float
    end_seconds: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source_segment_indexes": self.source_segment_indexes,
            "source_segment_start": self.source_segment_indexes[0],
            "source_segment_end": self.source_segment_indexes[-1],
            "start_seconds": round(self.start_seconds, 3),
            "end_seconds": round(self.end_seconds, 3),
        }


@dataclass(frozen=True)
class ASRFactNormalizationResult:
    normalized_text: str
    normalized_sentences: list[dict[str, Any]]
    normalized_paragraphs: list[str]
    diagnostics: dict[str, Any]


def _cjk_len(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _body_character_sequence(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKC", value)
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def _protected_token_multiset(value: str) -> Counter[str]:
    normalized = _body_character_sequence(value)
    tokens: list[str] = []
    for pattern in (
        ARABIC_FACT_TOKEN_RE,
        CHINESE_TIME_QUANTITY_RE,
        RELATIVE_TIME_RE,
        LATIN_ACRONYM_RE,
        ORGANIZATION_RE,
    ):
        tokens.extend(match.group(0).strip().lower() for match in pattern.finditer(normalized))
    for term in PROTECTED_LITERAL_TERMS:
        tokens.extend(term.lower() for _ in range(normalized.count(term)))
    return Counter(token for token in tokens if token)


def _ends_with_continuation(value: str) -> bool:
    body = value.rstrip(TERMINATORS + CLAUSE_PUNCTUATION + " \t\r\n")
    return body.endswith(CONTINUATION_SUFFIXES)


def _paragraphs(sentences: list[NormalizedSentence]) -> list[str]:
    if not sentences:
        return []
    groups: list[list[NormalizedSentence]] = [sentences[index : index + 4] for index in range(0, len(sentences), 4)]
    if len(groups) > 1 and len(groups[-1]) < 3 and len(groups[-2]) + len(groups[-1]) <= 5:
        groups[-2].extend(groups.pop())
    return ["".join(sentence.text for sentence in group) for group in groups]


def _build_sentences(segments: list[Any]) -> list[NormalizedSentence]:
    sentences: list[NormalizedSentence] = []
    chars: list[str] = []
    indexes: list[int] = []
    starts: list[float] = []
    ends: list[float] = []

    def flush(*, force_terminal: bool = True) -> None:
        nonlocal chars, indexes, starts, ends
        text = "".join(chars).strip()
        if not text:
            chars, indexes, starts, ends = [], [], [], []
            return
        if force_terminal and text[-1] not in TERMINATORS:
            if text[-1] in CLAUSE_PUNCTUATION:
                text = text[:-1] + "。"
            else:
                text += "。"
        ordered_indexes = list(dict.fromkeys(indexes))
        sentences.append(
            NormalizedSentence(
                text=text,
                source_segment_indexes=ordered_indexes,
                start_seconds=min(starts),
                end_seconds=max(ends),
            )
        )
        chars, indexes, starts, ends = [], [], [], []

    for position, segment in enumerate(segments):
        text = str(getattr(segment, "text", "") or "")
        segment_index = int(getattr(segment, "segment_index", position))
        start = float(getattr(segment, "start", 0.0) or 0.0)
        end = float(getattr(segment, "end", start) or start)
        for char in text:
            if char.isspace():
                continue
            chars.append(char)
            indexes.append(segment_index)
            starts.append(start)
            ends.append(end)
            current = "".join(chars)
            current_cjk = _cjk_len(current)
            if char in TERMINATORS:
                flush(force_terminal=False)
            elif char in CLAUSE_PUNCTUATION and current_cjk >= TARGET_SENTENCE_CJK and not _ends_with_continuation(current):
                flush()
            elif current_cjk >= MAX_SENTENCE_CJK and not _ends_with_continuation(current):
                flush()

        if not chars or position + 1 >= len(segments):
            continue
        next_segment = segments[position + 1]
        gap = max(0.0, float(getattr(next_segment, "start", end) or end) - end)
        current = "".join(chars)
        current_cjk = _cjk_len(current)
        if (
            gap >= PAUSE_BOUNDARY_SECONDS
            and current_cjk >= MIN_SENTENCE_CJK
            and not _ends_with_continuation(current)
        ):
            flush()
    flush()
    return sentences


def _validate_normalization(corrected_text: str, normalized_text: str) -> tuple[bool, bool]:
    character_sequence_preserved = _body_character_sequence(corrected_text) == _body_character_sequence(normalized_text)
    protected_token_multiset_preserved = _protected_token_multiset(corrected_text) == _protected_token_multiset(normalized_text)
    return character_sequence_preserved, protected_token_multiset_preserved


def normalize_asr_for_fact_ledger(
    corrected_segments: Iterable[Any],
    corrected_transcript: str,
    *,
    raw_transcript: str | None = None,
    raw_segment_count: int | None = None,
) -> ASRFactNormalizationResult:
    segments = list(corrected_segments)
    raw_text = corrected_transcript if raw_transcript is None else raw_transcript
    candidate_sentences = _build_sentences(segments)
    candidate_paragraphs = _paragraphs(candidate_sentences)
    candidate_text = "\n\n".join(candidate_paragraphs)
    character_preserved, protected_preserved = _validate_normalization(corrected_transcript, candidate_text)
    validation_passed = bool(candidate_text and character_preserved and protected_preserved)
    fallback_reason = ""
    normalization_applied = validation_passed and candidate_text != corrected_transcript

    if validation_passed:
        sentences = candidate_sentences
        paragraphs = candidate_paragraphs
        normalized_text = candidate_text
    else:
        fallback_reason = "normalization_validation_failed"
        normalized_text = corrected_transcript
        fallback_sentence = NormalizedSentence(
            text=corrected_transcript.strip(),
            source_segment_indexes=list(range(len(segments))),
            start_seconds=min((float(getattr(item, "start", 0.0) or 0.0) for item in segments), default=0.0),
            end_seconds=max((float(getattr(item, "end", 0.0) or 0.0) for item in segments), default=0.0),
        )
        sentences = [fallback_sentence] if fallback_sentence.text else []
        paragraphs = [fallback_sentence.text] if fallback_sentence.text else []

    sentence_dicts = [sentence.as_dict() for sentence in sentences]
    diagnostics = {
        "raw_segment_count": int(raw_segment_count if raw_segment_count is not None else len(segments)),
        "corrected_segment_count": len(segments),
        "raw_transcript_chars": len(raw_text),
        "raw_transcript_cjk": _cjk_len(raw_text),
        "corrected_transcript_chars": len(corrected_transcript),
        "corrected_transcript_cjk": _cjk_len(corrected_transcript),
        "raw_newline_count": raw_text.count("\n"),
        "corrected_newline_count": corrected_transcript.count("\n"),
        "normalized_sentence_count": len(sentences),
        "normalized_paragraph_count": len(paragraphs),
        "normalized_fact_count": len(sentences),
        "normalized_text_chars": len(normalized_text),
        "normalized_text_cjk": _cjk_len(normalized_text),
        "normalization_applied": normalization_applied,
        "normalization_validation_passed": validation_passed,
        "normalization_fallback_reason": fallback_reason,
        "raw_text_sha256": _sha256(raw_text),
        "corrected_text_sha256": _sha256(corrected_transcript),
        "normalized_text_sha256": _sha256(normalized_text),
        "character_sequence_preserved": character_preserved,
        "protected_token_multiset_preserved": protected_preserved,
        "normalized_sentence_ranges": [
            {key: value for key, value in sentence.items() if key != "text"}
            for sentence in sentence_dicts
        ],
    }
    return ASRFactNormalizationResult(
        normalized_text=normalized_text,
        normalized_sentences=sentence_dicts,
        normalized_paragraphs=paragraphs,
        diagnostics=diagnostics,
    )
