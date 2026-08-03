from __future__ import annotations

import asyncio
from pathlib import Path
import re
import unicodedata

from app.services import asr_fact_normalization, viral_pipeline
from app.services.asr_fact_normalization import normalize_asr_for_fact_ledger
from app.services.asr_service import ASRResult, ASRSegment
from app.services.financial_transcript import CorrectionResult
from app.services.viral_fact_fidelity import build_source_fact_ledger
from scripts.p2_37_text_acceptance import EMOTIONAL_FIXTURE, FINANCE_FIXTURE


def _cjk_len(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


def _body_sequence(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKC", value)
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def _split_into_segments(value: str, count: int, *, seconds: float = 167.6) -> list[ASRSegment]:
    boundaries = [round(index * len(value) / count) for index in range(count + 1)]
    return [
        ASRSegment(
            start=index * seconds / count,
            end=(index + 1) * seconds / count,
            text=value[boundaries[index] : boundaries[index + 1]],
        )
        for index in range(count)
    ]


def _sparse_finance_fixture() -> tuple[list[ASRSegment], str]:
    sparse = re.sub(r"[。！？!?；;]", "", FINANCE_FIXTURE.replace("\n", ""))
    segments = _split_into_segments(sparse, 70)
    return segments, "\n".join(segment.text for segment in segments)


def test_real_video_shape_is_normalized_into_traceable_facts():
    segments, corrected = _sparse_finance_fixture()
    before = build_source_fact_ledger(corrected)
    result = normalize_asr_for_fact_ledger(
        segments,
        corrected,
        raw_transcript=corrected,
        raw_segment_count=70,
    )
    after = build_source_fact_ledger(result.normalized_text, result.normalized_sentences)

    assert len(segments) == 70
    assert corrected.count("\n") == 69
    assert _cjk_len(corrected) == 749
    assert before["fact_count"] == 1
    assert 1 < after["fact_count"] < 70
    assert _body_sequence(corrected) == _body_sequence(result.normalized_text)
    assert result.diagnostics["character_sequence_preserved"] is True
    assert result.diagnostics["protected_token_multiset_preserved"] is True
    assert all(fact["evidence"].count("\n") == 0 for fact in after["facts"])
    assert all(fact["source_segment_indexes"] for fact in after["facts"])
    assert all(fact["start_seconds"] <= fact["end_seconds"] for fact in after["facts"])
    assert all(
        indexes == list(range(indexes[0], indexes[-1] + 1))
        for indexes in (fact["source_segment_indexes"] for fact in after["facts"])
    )


def test_existing_text_fixture_keeps_twenty_one_facts_without_asr_normalization():
    ledger = build_source_fact_ledger(FINANCE_FIXTURE)
    assert _cjk_len(FINANCE_FIXTURE) == 749
    assert ledger["fact_count"] == 21


def test_low_density_emotional_copy_keeps_short_sentence_rhythm():
    segments = _split_into_segments(EMOTIONAL_FIXTURE.replace("\n", ""), 24, seconds=120)
    corrected = "\n".join(segment.text for segment in segments)
    result = normalize_asr_for_fact_ledger(segments, corrected)

    assert _body_sequence(corrected) == _body_sequence(result.normalized_text)
    assert result.diagnostics["normalized_sentence_count"] >= 15
    assert max(_cjk_len(item["text"]) for item in result.normalized_sentences) <= 54
    assert not any(term in result.normalized_text for term in ("ETF", "回购", "投资", "买入"))


def test_complete_punctuation_is_idempotent():
    text = "先看现象。再核对条件！最后保留边界？这是完整结论；不要匆忙行动。"
    first = normalize_asr_for_fact_ledger([ASRSegment(0, 8, text)], text)
    second = normalize_asr_for_fact_ledger([ASRSegment(0, 8, first.normalized_text)], first.normalized_text)
    assert second.normalized_text == first.normalized_text
    assert second.normalized_sentences == first.normalized_sentences


def test_validation_failure_uses_corrected_transcript_and_reports_fallback(monkeypatch):
    segments, corrected = _sparse_finance_fixture()
    monkeypatch.setattr(asr_fact_normalization, "_validate_normalization", lambda *_args: (False, False))
    result = normalize_asr_for_fact_ledger(segments, corrected)

    assert result.normalized_text == corrected
    assert result.diagnostics["normalization_validation_passed"] is False
    assert result.diagnostics["normalization_fallback_reason"] == "normalization_validation_failed"


def test_single_long_unpunctuated_segment_is_deterministically_split():
    text = "这是一段没有终止标点但是需要保持所有正文字符顺序的知识口播内容" * 12
    result = normalize_asr_for_fact_ledger([ASRSegment(0, 60, text)], text)

    assert 1 < len(result.normalized_sentences) < 20
    assert _body_sequence(text) == _body_sequence(result.normalized_text)
    assert all(_cjk_len(item["text"]) <= 54 for item in result.normalized_sentences)
    assert result.normalized_text.rstrip().endswith("。")


def test_segment_mapping_spans_are_ordered_and_contiguous():
    segments = [
        ASRSegment(0, 1, "这是第一段需要继续说明的内容"),
        ASRSegment(1, 2, "仍然没有结束需要合并"),
        ASRSegment(2.8, 4, "停顿之后形成新句。"),
    ]
    corrected = "\n".join(segment.text for segment in segments)
    result = normalize_asr_for_fact_ledger(segments, corrected)

    assert result.normalized_sentences[0]["source_segment_indexes"] == [0, 1]
    assert result.normalized_sentences[0]["start_seconds"] == 0
    assert result.normalized_sentences[0]["end_seconds"] == 2
    assert result.normalized_sentences[-1]["source_segment_indexes"] == [2]
    assert result.normalized_sentences[-1]["start_seconds"] == 2.8
    assert result.normalized_sentences[-1]["end_seconds"] == 4


def test_video_pipeline_passes_normalized_text_and_fact_mapping_without_llm(monkeypatch, tmp_path: Path):
    segments, corrected = _sparse_finance_fixture()
    observed = {}
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.wav"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")

    async def fake_correction(_segments, _language):
        return CorrectionResult(
            corrected_transcript=corrected,
            corrected_segments=segments,
            corrections=[],
            review_segments=[],
            quality_passed=True,
            provider="fixture",
        )

    async def fake_analysis(_supabase, **kwargs):
        observed.update(kwargs)
        ledger = build_source_fact_ledger(kwargs["raw_script"], kwargs["source_fact_sentences"])
        observed["ledger"] = ledger
        return {
            "topic": "fixture",
            "rewrites": [{"title": "AI改写稿", "script": "这是不调用模型的测试结果。"}],
            "diagnostics": {"source_cjk": 749},
            "generated_count": 1,
            "requested_count": 3,
            "filtered_invalid_count": 2,
        }

    monkeypatch.setattr(viral_pipeline.settings, "viral_asr_domain", "financial")
    monkeypatch.setattr(viral_pipeline, "extract_audio", lambda *_args: asyncio.sleep(0, result=audio))
    monkeypatch.setattr(
        viral_pipeline,
        "transcribe_audio",
        lambda *_args: asyncio.sleep(
            0,
            result=ASRResult(
                ok=True,
                transcript=corrected,
                segments=segments,
                coverage_seconds=167.6,
                last_timestamp_seconds=167.6,
                raw_segment_count=70,
            ),
        ),
    )
    monkeypatch.setattr(viral_pipeline, "correct_financial_transcript", fake_correction)
    monkeypatch.setattr(viral_pipeline, "analyze_viral_script", fake_analysis)

    result = asyncio.run(
        viral_pipeline._process_video_path(
            object(),
            video_path=video,
            work_dir=tmp_path,
            user_id="fixture-user",
            email="fixture@example.invalid",
            source_url="",
            industry="knowledge",
            language="zh",
            rewrite_length="match_source",
            source_type="uploaded_video_asr",
            metadata={"duration": 170.333},
        )
    )

    assert result["ok"] is True
    assert observed["raw_script"].count("\n") < corrected.count("\n")
    assert 1 < observed["ledger"]["fact_count"] < 70
    assert result["diagnostics"]["normalized_fact_count"] == observed["ledger"]["fact_count"]
    assert result["diagnostics"]["normalization_validation_passed"] is True
