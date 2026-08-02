import asyncio

import pytest
from fastapi import HTTPException

from app.services import viral_analyzer
from app.services.viral_length import (
    MAX_DYNAMIC_TARGET_CJK,
    calculate_public_metadata_target,
    calculate_rewrite_length_target,
)
from scripts.p2_37_text_acceptance import EMOTIONAL_FIXTURE, FINANCE_FIXTURE


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


def _source_flow_response(
    payload,
    *,
    initial_lengths,
    reviewed_lengths=None,
    repaired_lengths=None,
    repair_response=None,
):
    if "variant_task" in payload:
        index = payload["variant_task"]["index"]
        response = {
            "rewrite": {
                "title": f"版本{index + 1}",
                "script": chr(ord("甲") + index) * initial_lengths[index] + "。",
                "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
            }
        }
        if index == 0:
            response["analysis"] = {
                key: value
                for key, value in _analysis_with_lengths(initial_lengths).items()
                if key != "rewrites"
            }
        return response
    if "current_rewrites" in payload and "source_fact_ledger" in payload:
        lengths = reviewed_lengths or initial_lengths
        return {
            "reviews": [
                {
                    "index": index,
                    "audited_script": chr(ord("甲") + index) * lengths[index] + "。",
                    "removed_unsupported_claims": [],
                    "unsupported_spans": [],
                    "unsupported_remaining": False,
                    "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
                }
                for index in range(3)
            ]
        }
    if "current_script" in payload:
        if repair_response is not None:
            return repair_response
        index = payload["variant"]["index"]
        return {
            "repaired_script": chr(ord("甲") + index) * repaired_lengths[index] + "。",
            "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
            "replacements": [],
            "unsupported_spans": [],
            "unsupported_remaining": False,
        }
    return _analysis_with_lengths(initial_lengths)


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
    monkeypatch.setattr(
        viral_analyzer,
        "map_source_fact_coverage",
        lambda ledger, _script, **_kwargs: {
            "directly_supported_fact_ids": ledger["fact_ids"][:8],
            "uncertain_fact_ids": [],
            "unsupported_spans": [],
        },
    )
    monkeypatch.setattr(viral_analyzer, "unsupported_hard_facts", lambda *_args: [])


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
    assert viral_analyzer._cjk_len(FINANCE_FIXTURE) == 749
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
    assert viral_analyzer._cjk_len(EMOTIONAL_FIXTURE) == 321
    target = calculate_rewrite_length_target(
        source_cjk=240,
        effective_speech_seconds=120,
        length_mode="match_source",
    )
    assert target.source_density == 2.0
    assert (target.target_min_chars, target.target_max_chars) == (216, 264)


def test_real_321_cjk_emotional_fixture_keeps_its_dynamic_range():
    target = calculate_rewrite_length_target(
        source_cjk=viral_analyzer._cjk_len(EMOTIONAL_FIXTURE),
        effective_speech_seconds=120,
        length_mode="match_source",
    )
    assert (target.target_min_chars, target.target_center_chars, target.target_max_chars) == (
        289,
        321,
        353,
    )


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
        return _source_flow_response(payload, initial_lengths=[700, 749, 800])

    _prepare(monkeypatch, fake_generate)
    result = _run()
    assert len(calls) == 4
    assert len([call for call in calls if "variant_task" in call]) == 3
    assert not [call for call in calls if "current_script" in call]
    assert result["diagnostic"]["actual_chars"] == [700, 749, 800]
    assert result["diagnostic"]["target_min_chars"] == 674
    assert result["diagnostic"]["target_max_chars"] == 824


def test_pasted_text_matches_source_length_without_claiming_speech_density(monkeypatch):
    async def fake_generate(_self, *, payload, **_kwargs):
        return _source_flow_response(payload, initial_lengths=[700, 749, 800])

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
        return _source_flow_response(
            payload,
            initial_lengths=[700, 500, 600],
            repaired_lengths=[700, 740, 700],
        )

    _prepare(monkeypatch, fake_generate)
    result = _run()
    repairs = [call for call in calls if "current_script" in call]
    assert sorted(call["variant"]["index"] for call in repairs) == [1, 2]
    assert all("unused_source_fact_ids" in call for call in repairs)
    assert all("禁止自由扩写" not in " ".join(call["requirements"]) for call in repairs)
    assert result["diagnostic"]["actual_chars"] == [700, 740, 700]


def test_source_constrained_repair_replaces_low_yield_rounds(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        return _source_flow_response(
            payload,
            initial_lengths=[500, 500, 500],
            repaired_lengths=[700, 700, 700],
        )

    _prepare(monkeypatch, fake_generate)
    result = _run()
    assert len([call for call in calls if "current_script" in call]) == 3
    assert not [call for call in calls if "supplements_requested" in call]
    assert result["diagnostic"]["actual_chars"] == [700, 700, 700]


def test_overlong_initial_rewrites_are_fact_reviewed_and_compressed(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        return _source_flow_response(
            payload,
            initial_lengths=[900, 910, 920],
            reviewed_lengths=[760, 760, 760],
        )

    _prepare(monkeypatch, fake_generate)
    result = _run()
    assert len(calls) == 4
    assert result["diagnostic"]["actual_chars"] == [760, 760, 760]
    assert result["diagnostic"]["stage_timings"][1]["stage"] == "fact_review"
    assert all(item["script"].endswith("。") for item in result["rewrites"])


@pytest.mark.parametrize(
    "repair_response",
    [{}, {"repaired_script": ""}, {"repaired_script": "太短。", "unsupported_remaining": True}],
)
def test_empty_or_missing_repair_fields_use_deterministic_source_scaffold(monkeypatch, repair_response):
    async def fake_generate(_self, *, payload, **_kwargs):
        return _source_flow_response(
            payload,
            initial_lengths=[500, 500, 500],
            repaired_lengths=[700, 700, 700],
            repair_response=repair_response,
        )

    _prepare(monkeypatch, fake_generate)
    result = _run()
    assert all(
        674 <= length <= 824 for length in result["diagnostic"]["actual_chars"]
    )
    assert result["diagnostic"]["fact_fidelity"]["final_source_reconstruction"] == []
    assert result["diagnostic"]["primary_selection"]["succeeded"] is False
    assert result["diagnostic"]["scaffold_polish"]["attempted"] is True
    assert result["generated_count"] == 1
    assert result["rewrites"][0]["provenance"] == "deterministic_scaffold"
    assert result["diagnostic"]["fact_fidelity"]["hard_violations_after"] == [
        [],
        [],
        [],
    ]


def test_public_metadata_never_claims_exact_duration_match():
    target = calculate_public_metadata_target(evidence_cjk=80)
    assert target.length_mode == "public_metadata_fallback"
    assert target.exact_duration_match is False
    assert target.effective_speech_seconds is None
