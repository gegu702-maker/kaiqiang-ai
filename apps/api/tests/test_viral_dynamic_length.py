import asyncio

import pytest
from fastapi import HTTPException

from app.services import viral_analyzer
from app.services.viral_length import (
    MAX_DYNAMIC_TARGET_CJK,
    calculate_public_metadata_target,
    calculate_rewrite_length_target,
)


class _Table:
    def insert(self, _payload):
        return self

    def execute(self):
        return None


class _Supabase:
    def table(self, _name):
        return _Table()


def _analysis_with_lengths(lengths):
    return {
        "topic": "主题",
        "hook": "钩子",
        "selling_points": ["痛点", "反差", "好奇", "利益"],
        "structure": ["开头", "问题", "解释", "案例", "结尾"],
        "template": "模板",
        "core_points": ["观点"],
        "arguments": ["论据"],
        "cases": [],
        "data_points": [],
        "rewrites": [
            {"title": f"版本{index + 1}", "script": chr(ord("甲") + index) * length + "。"}
            for index, length in enumerate(lengths)
        ],
    }


def _preserve(payload, *, language):
    assert language == "zh"
    return payload


def _prepare(monkeypatch, fake_generate):
    monkeypatch.setattr(
        viral_analyzer,
        "_assert_viral_quota",
        lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99},
    )
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    monkeypatch.setattr(viral_analyzer, "validate_viral_analysis_payload", _preserve)


def _run(*, raw_script="源" * 749, rewrite_length="match_source", seconds=167.6):
    return asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            raw_script=raw_script,
            industry="knowledge",
            language="zh",
            rewrite_length=rewrite_length,
            effective_speech_seconds=seconds,
        )
    )


def test_match_source_targets_real_749_cjk_fixture():
    target = calculate_rewrite_length_target(
        source_cjk=749,
        effective_speech_seconds=167.6,
        length_mode="match_source",
    )
    assert (target.target_min_chars, target.target_center_chars, target.target_max_chars) == (674, 749, 824)
    assert target.source_density == 4.469


def test_match_source_targets_120_seconds_at_same_density():
    target = calculate_rewrite_length_target(
        source_cjk=536,
        effective_speech_seconds=120,
        length_mode="match_source",
    )
    assert (target.target_min_chars, target.target_center_chars, target.target_max_chars) == (482, 536, 590)
    assert target.source_density == 4.467


def test_low_density_emotional_video_is_not_raised_to_finance_density():
    target = calculate_rewrite_length_target(
        source_cjk=240,
        effective_speech_seconds=120,
        length_mode="match_source",
    )
    assert target.source_density == 2.0
    assert (target.target_min_chars, target.target_max_chars) == (216, 264)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("concise", (487, 543, 599)),
        ("moderate_expand", (824, 899, 974)),
    ],
)
def test_requested_modes_use_source_ratios(mode, expected):
    target = calculate_rewrite_length_target(source_cjk=749, length_mode=mode)
    assert (target.target_min_chars, target.target_center_chars, target.target_max_chars) == expected


def test_dynamic_targets_have_short_and_long_resource_bounds():
    short = calculate_rewrite_length_target(source_cjk=20, length_mode="match_source")
    long = calculate_rewrite_length_target(source_cjk=5000, length_mode="match_source")
    assert short.target_min_chars == 40
    assert short.target_center_chars == 60
    assert short.target_max_chars == 80
    assert long.target_max_chars == MAX_DYNAMIC_TARGET_CJK
    assert long.target_min_chars <= long.target_center_chars <= long.target_max_chars


def test_in_range_initial_rewrites_do_not_trigger_repair(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        return _analysis_with_lengths([700, 749, 800])

    _prepare(monkeypatch, fake_generate)
    result = _run()
    assert len(calls) == 1
    assert result["diagnostic"]["actual_chars"] == [700, 749, 800]
    assert result["diagnostic"]["target_min_chars"] == 674
    assert result["diagnostic"]["target_max_chars"] == 824


def test_pasted_text_matches_source_length_without_claiming_speech_density(monkeypatch):
    async def fake_generate(_self, **_kwargs):
        return _analysis_with_lengths([700, 749, 800])

    _prepare(monkeypatch, fake_generate)
    result = _run(seconds=None)
    assert result["diagnostic"]["source_cjk"] == 749
    assert result["diagnostic"]["effective_speech_seconds"] is None
    assert result["diagnostic"]["source_density"] is None
    assert (result["diagnostic"]["target_min_chars"], result["diagnostic"]["target_max_chars"]) == (674, 824)


def test_only_deficient_versions_receive_missing_source_information(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "supplements_requested" not in payload:
            return _analysis_with_lengths([700, 500, 600])
        return {
            "supplements": [
                {
                    "index": item["index"],
                    "title": item["title"],
                    "additional_script": ("乙" * 240 if item["index"] == 1 else "丙" * 100) + "。",
                }
                for item in payload["supplements_requested"]
            ]
        }

    _prepare(monkeypatch, fake_generate)
    result = _run()
    assert [item["index"] for item in calls[1]["supplements_requested"]] == [1, 2]
    assert "只补原转写中已有" in " ".join(calls[1]["requirements"])
    assert result["diagnostic"]["actual_chars"] == [700, 740, 700]


def test_second_round_uses_observed_yield_and_reaches_dynamic_range(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "supplements_requested" not in payload:
            return _analysis_with_lengths([500, 500, 500])
        addition = 50 if payload["supplement_round"] == 1 else 150
        return {
            "supplements": [
                {
                    "index": item["index"],
                    "title": item["title"],
                    "additional_script": chr(ord("丁") + item["index"]) * addition + "。",
                }
                for item in payload["supplements_requested"]
            ]
        }

    _prepare(monkeypatch, fake_generate)
    result = _run()
    assert calls[2]["supplement_round"] == 2
    assert all(item["planning_yield_rate"] == 0.1 for item in calls[2]["supplements_requested"])
    assert result["diagnostic"]["actual_chars"] == [700, 700, 700]


def test_overlong_initial_rewrites_are_deduplicated_and_compressed(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "current_rewrites" not in payload:
            return _analysis_with_lengths([900, 910, 920])
        assert "compressions" in payload["schema"]
        return {
            "compressions": [
                {
                    "index": item["index"],
                    "compressed_script": chr(ord("丁") + item["index"]) * 760 + "。",
                }
                for item in payload["current_rewrites"]
            ]
        }

    _prepare(monkeypatch, fake_generate)
    result = _run()
    assert len(calls) == 2
    assert result["diagnostic"]["actual_chars"] == [760, 760, 760]
    assert result["diagnostic"]["length_repair_rounds"][1]["stage"] == "compressing"
    assert all(item["script"].endswith("。") for item in result["rewrites"])


@pytest.mark.parametrize("repair_response", [{}, {"supplements": []}, {"supplements": [{"title": "缺index"}]}])
def test_empty_or_missing_repair_fields_end_in_structured_failure(monkeypatch, repair_response):
    async def fake_generate(_self, *, payload, **_kwargs):
        if "supplements_requested" not in payload:
            return _analysis_with_lengths([500, 500, 500])
        return repair_response

    _prepare(monkeypatch, fake_generate)
    with pytest.raises(HTTPException) as raised:
        _run()
    detail = raised.value.detail
    assert detail["code"] == "analysis_output_out_of_range"
    assert detail["target_min_chars"] == 674
    assert detail["target_center_chars"] == 749
    assert detail["target_max_chars"] == 824
    assert len(detail["length_repair_rounds"]) == 3


def test_public_metadata_never_claims_exact_duration_match():
    target = calculate_public_metadata_target(evidence_cjk=80)
    assert target.length_mode == "public_metadata_fallback"
    assert target.exact_duration_match is False
    assert target.effective_speech_seconds is None
