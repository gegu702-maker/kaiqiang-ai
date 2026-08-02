import asyncio

import pytest
from fastapi import HTTPException

from app.services import viral_analyzer
from app.services.viral_fact_fidelity import (
    build_source_fact_ledger,
    map_source_fact_coverage,
    unsupported_hard_facts,
)
from app.services.llm_provider import LLMProviderError
from scripts.p2_37_text_acceptance import FINANCE_FIXTURE


class _Table:
    def insert(self, _payload):
        return self

    def execute(self):
        return None


class _Supabase:
    def table(self, _name):
        return _Table()


def _analysis(scripts):
    return {
        "topic": "资本市场信号",
        "hook": "不要把信号当结论",
        "selling_points": ["机构表态", "回购", "机构自购", "中报"],
        "structure": ["开头", "保险", "回购", "中报", "风险"],
        "template": "先看信号，再核对条件。",
        "core_points": ["信心正在从表达走向部分行动"],
        "arguments": ["仍需核对公告、经营数据与资金流向"],
        "cases": [],
        "data_points": [],
        "rewrites": [
            {"title": title, "script": script}
            for title, script in zip(
                ("版本A：热点反差版", "版本B：用户痛点版", "版本C：商业机会版"),
                scripts,
                strict=True,
            )
        ],
    }


def _sized(prefix, filler, length):
    prefix_chars = viral_analyzer._cjk_len(prefix)
    return prefix + filler * max(0, length - prefix_chars) + "。"


def _initial_variant(payload, scripts):
    index = payload["variant_task"]["index"]
    response = {
        "rewrite": {
            "title": f"版本{index + 1}",
            "script": scripts[index],
            "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
        }
    }
    if index == 0:
        response["analysis"] = {
            key: value for key, value in _analysis(scripts).items() if key != "rewrites"
        }
    return response


def _run(monkeypatch, fake_generate):
    monkeypatch.setattr(
        viral_analyzer,
        "_assert_viral_quota",
        lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99},
    )
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    monkeypatch.setattr(viral_analyzer, "validate_viral_analysis_payload", lambda payload, **_kwargs: payload)
    return asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            raw_script=FINANCE_FIXTURE,
            industry="knowledge",
            language="zh",
            rewrite_length="match_source",
            effective_speech_seconds=167.6,
        )
    )


def _mock_source_coverage(monkeypatch, *, patch_hard_facts=True):
    ledger = build_source_fact_ledger(FINANCE_FIXTURE)

    def fake_mapping(_ledger, script, *, claimed_fact_ids=None):
        marker = next((item for item in ("甲", "乙", "丙") if item in script), "甲")
        offsets = {"甲": 0, "乙": 6, "丙": 12}
        start = offsets[marker]
        ids = ledger["fact_ids"][start : start + 8]
        if len(ids) < 8:
            ids = ledger["fact_ids"][-8:]
        return {
            "directly_supported_fact_ids": ids,
            "uncertain_fact_ids": [],
            "unsupported_spans": [],
        }

    monkeypatch.setattr(viral_analyzer, "map_source_fact_coverage", fake_mapping)
    if patch_hard_facts:
        monkeypatch.setattr(viral_analyzer, "unsupported_hard_facts", lambda *_args: [])


def _contract_provider(scripts, diversified=None):
    diversified = diversified or {}

    async def fake_generate(_self, *, payload, **_kwargs):
        if "variant_task" in payload:
            return _initial_variant(payload, scripts)
        if "current_rewrites" in payload:
            return {
                "reviews": [
                    {
                        "index": index,
                        "audited_script": script,
                        "removed_unsupported_claims": [],
                        "unsupported_spans": [],
                        "unsupported_remaining": False,
                        "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
                    }
                    for index, script in enumerate(scripts)
                ]
            }
        if "current_duplicate_variant" in payload:
            index = payload["current_duplicate_variant"].get("title", "")
            script = diversified.get(index, payload["current_duplicate_variant"]["script"])
            return {
                "diversified_script": script,
                "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
            }
        raise AssertionError(f"unexpected payload keys: {sorted(payload)}")

    return fake_generate


@pytest.mark.parametrize(
    ("scripts", "expected_count", "expected_duplicates"),
    [
        ([_sized("同一主稿", "甲", 700)] * 3, 1, 2),
        ([_sized("主稿", "甲", 700), _sized("痛点", "乙", 710), _sized("主稿", "甲", 700)], 2, 1),
        ([_sized("主稿", "甲", 700), _sized("痛点", "乙", 710), _sized("分析", "丙", 720)], 3, 0),
    ],
)
def test_progressive_variant_deduplication_contract(
    monkeypatch,
    scripts,
    expected_count,
    expected_duplicates,
):
    _mock_source_coverage(monkeypatch)
    result = _run(monkeypatch, _contract_provider(scripts))

    assert result["generated_count"] == expected_count
    assert len(result["rewrites"]) == expected_count
    assert result["filtered_duplicate_count"] == expected_duplicates
    assert result["degraded"] is (expected_count < 3)
    similarity_failures = [
        item
        for item in result["diagnostic"]["candidate_failure_diagnostics"]
        if item["similarity_failure"]
    ]
    assert len(similarity_failures) == expected_duplicates
    assert all(item["fact_fidelity"]["valid"] for item in result["rewrites"])
    assert all(674 <= item["actual_chars"] <= 824 for item in result["rewrites"])
    for left in range(expected_count):
        for right in range(left + 1, expected_count):
            assert viral_analyzer.rewrite_similarity(
                result["rewrites"][left]["script"],
                result["rewrites"][right]["script"],
            ) <= viral_analyzer.MAX_VARIANT_SIMILARITY


def test_valid_primary_survives_two_invalid_optional_variants(monkeypatch):
    _mock_source_coverage(monkeypatch)
    scripts = [_sized("主稿", "甲", 700), "太短。", "也太短。"]

    async def fake_generate(_self, *, payload, **_kwargs):
        if "variant_task" in payload:
            return _initial_variant(payload, scripts)
        if "current_rewrites" in payload:
            return {
                "reviews": [
                    {
                        "index": index,
                        "audited_script": script,
                        "removed_unsupported_claims": [],
                        "unsupported_spans": [],
                        "unsupported_remaining": False,
                        "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
                    }
                    for index, script in enumerate(scripts)
                ]
            }
        if "current_script" in payload:
            return {
                "repaired_script": "仍然太短。",
                "used_source_fact_ids": [],
                "replacements": [],
                "unsupported_spans": [],
                "unsupported_remaining": False,
            }
        if "current_version" in payload:
            return {
                "reconstructed_script": "还是太短。",
                "used_source_fact_ids": [],
                "unsupported_spans": [],
                "unsupported_remaining": False,
            }
        raise AssertionError(f"unexpected payload keys: {sorted(payload)}")

    result = _run(monkeypatch, fake_generate)
    assert result["generated_count"] == 1
    assert result["filtered_invalid_count"] == 2
    assert result["rewrites"][0]["script"] == scripts[0]


def test_all_initial_models_fail_returns_one_scaffold(monkeypatch):
    async def fake_generate(_self, **_kwargs):
        raise LLMProviderError(
            code="llm_auth_error",
            message="provider unavailable",
            retryable=False,
        )

    result = _run(monkeypatch, fake_generate)
    assert result["generated_count"] == 1
    assert result["rewrites"][0]["provenance"] == "deterministic_scaffold"
    assert result["variants"] == result["rewrites"]


def test_all_models_and_scaffold_invalid_is_the_only_whole_request_failure(monkeypatch):
    async def fake_generate(_self, **_kwargs):
        raise LLMProviderError(
            code="llm_auth_error",
            message="provider unavailable",
            retryable=False,
        )

    monkeypatch.setattr(viral_analyzer, "_source_backed_scaffold", lambda **_kwargs: "")
    with pytest.raises(HTTPException) as raised:
        _run(monkeypatch, fake_generate)
    assert raised.value.status_code == 502
    assert raised.value.detail["stage"] == "final_variant_validation"


def test_optional_variants_need_minimum_not_full_fact_coverage_and_union_is_recorded(monkeypatch):
    _mock_source_coverage(monkeypatch)
    scripts = [_sized("主稿", "甲", 700), _sized("痛点", "乙", 710), _sized("分析", "丙", 720)]
    result = _run(monkeypatch, _contract_provider(scripts))

    assert all(item["source_fact_coverage"]["used_count"] == 8 for item in result["rewrites"])
    assert all(item["source_fact_coverage"]["used_count"] < 21 for item in result["rewrites"])
    expected_union = {
        fact_id
        for item in result["rewrites"]
        for fact_id in item["source_fact_coverage"]["directly_supported_fact_ids"]
    }
    assert set(result["union_source_fact_coverage"]["directly_supported_fact_ids"]) == expected_union


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("过去一个月某公司宣布回购，三个月后完成比例超过80%，股价慢慢修复。", {"过去一个月", "三个月后", "80%", "股价慢慢修复"}),
        ("半年后回购完成不到10%，再看ROE是否稳定。", {"半年后", "10%", "ROE"}),
        ("进入前十大流通股东名单，ETF份额连续四周增长。", {"前十大", "前十大流通股东", "ETF份额", "连续四周"}),
        ("某公司已经采取行动。", {"某公司"}),
    ],
)
def test_unsupported_numbers_times_cases_and_indicators_are_hard_violations(output, expected):
    violations = unsupported_hard_facts(FINANCE_FIXTURE, output)
    assert expected <= {item["value"] for item in violations}


def test_source_numbers_institutions_and_indicators_remain_allowed():
    supported = (
        "五大保险机构讨论稳定预期。沪深三百、中证五百、科创五十的结构不同。"
        "ETF申购可以观察，花旗集团和摩根士丹利的假设未必相同。"
    )
    assert unsupported_hard_facts(FINANCE_FIXTURE, supported) == []
    assert unsupported_hard_facts(FINANCE_FIXTURE, "科创50的公司结构不同。") == []
    ledger = build_source_fact_ledger(FINANCE_FIXTURE)
    assert ledger["fact_count"] == 21
    assert {
        "机构及表态",
        "回购及限定条件",
        "自购与ETF",
        "中报和产业链",
        "外资观点",
        "风险边界",
    } <= {item["category"] for item in ledger["facts"]}
    assert all(item["evidence"] in FINANCE_FIXTURE for item in ledger["facts"])
    assert "一天" in ledger["hard_fact_tokens"]
    assert "ETF" in ledger["hard_fact_tokens"]
    assert any("花旗集团" in item for item in ledger["organizations"])
    assert any("摩根士丹利" in item for item in ledger["organizations"])


def test_financial_fact_review_repairs_all_versions_and_preserves_dynamic_range(monkeypatch):
    _mock_source_coverage(monkeypatch, patch_hard_facts=False)
    calls = []
    bad_scripts = [
        "市场" * 170 + "过去一个月某公司宣布回购，三个月后完成比例超过80%，股价慢慢修复。" + "风险" * 155 + "。",
        "用户" * 170 + "半年后回购完成不到10%，再看ROE是否稳定。" + "核对" * 160 + "。",
        "机会" * 170 + "进入前十大流通股东名单，ETF份额连续四周增长。" + "边界" * 158 + "。",
    ]
    clean_scripts = [
        _sized("反差在于机构表达信心不等于短期涨跌承诺", "甲", 700),
        _sized("普通用户的痛点是容易把机构动作当成自己的投资结论", "乙", 720),
        _sized("观察角度要把保险回购机构自购中报和外资观点分别验证", "丙", 740),
    ]

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "variant_task" in payload:
            return _initial_variant(payload, bad_scripts)
        if "current_script" in payload:
            raise AssertionError("审查结果已合格，不应修复")
        requirements = " ".join(payload["requirements"])
        for prohibited in ("虚构公司", "完成比例", "ROE", "股东名单", "ETF份额", "目标价调整"):
            assert prohibited in requirements
        return {
            "reviews": [
                {
                    "index": index,
                    "audited_script": script,
                    "removed_unsupported_claims": [
                        {
                            "span": "原无来源片段",
                            "category": "案例",
                            "reason": "原始转写不支持该内容",
                        }
                    ],
                    "unsupported_spans": [],
                    "unsupported_remaining": False,
                    "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
                }
                for index, script in enumerate(clean_scripts)
            ]
        }

    result = _run(monkeypatch, fake_generate)
    assert len(calls) == 4
    assert len({item["script"][:12] for item in result["rewrites"]}) == 3
    assert all(674 <= length <= 824 for length in result["diagnostic"]["actual_chars"])
    fidelity = result["diagnostic"]["fact_fidelity"]
    assert fidelity["reviewed"] is True
    assert all(fidelity["hard_violations_before"])
    assert fidelity["hard_violations_after"] == [[], [], []]
    assert fidelity["unsupported_remaining"] == []
    assert all(fidelity["removed_claims"])


def test_fact_review_cannot_hide_a_fabricated_case_by_only_removing_its_number(monkeypatch):
    scripts = ["市场" * 350 + "。" for _ in range(3)]

    async def fake_generate(_self, *, payload, **_kwargs):
        if "variant_task" in payload:
            return _initial_variant(payload, scripts)
        if "current_script" in payload:
            return {
                "repaired_script": _sized("某公司回购后股价慢慢修复", "甲", 700),
                "used_source_fact_ids": payload["used_source_fact_ids"],
                "replacements": [],
                "unsupported_spans": [],
                "unsupported_remaining": False,
            }
        return {
            "reviews": [
                {
                    "index": index,
                    "audited_script": (
                        "市场" * 340 + "某公司回购后股价慢慢修复。" + "风险" * 10 + "。"
                        if index == 0
                        else "市场" * 350 + "。"
                    ),
                    "removed_unsupported_claims": [],
                    "unsupported_spans": [],
                    "unsupported_remaining": False,
                    "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
                }
                for index in range(3)
            ]
        }

    result = _run(monkeypatch, fake_generate)
    assert result["generated_count"] >= 1
    assert all(item["fact_fidelity"]["hard_violations"] == [] for item in result["rewrites"])
    assert all("某公司回购后股价慢慢修复" not in item["script"] for item in result["rewrites"])


def test_source_constrained_repair_restores_range_after_fact_review_is_short(monkeypatch):
    _mock_source_coverage(monkeypatch)
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        initial_scripts = ["市场" * 300 + "。", "用户" * 350 + "。", "机会" * 335 + "。"]
        if "variant_task" in payload:
            return _initial_variant(payload, initial_scripts)
        if "current_script" in payload:
            index = payload["variant"]["index"]
            return {
                "repaired_script": _sized(("反差", "痛点", "表达")[index], ("甲", "乙", "丙")[index], 700),
                "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
                "replacements": [],
                "unsupported_spans": [],
                "unsupported_remaining": False,
            }
        return {
            "reviews": [
                {
                    "index": index,
                    "audited_script": script,
                    "removed_unsupported_claims": [],
                    "unsupported_spans": [],
                    "unsupported_remaining": False,
                        "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
                }
                for index, script in enumerate(initial_scripts)
            ]
        }

    result = _run(monkeypatch, fake_generate)
    repairs = [call for call in calls if "current_script" in call]
    assert sorted(call["variant"]["index"] for call in repairs) == [0, 2]
    assert all("unused_source_fact_ids" in call for call in repairs)
    assert all(674 <= length <= 824 for length in result["diagnostic"]["actual_chars"])
    assert result["diagnostic"]["fact_fidelity"]["reviewed"] is True


def test_independent_generation_repairs_b_and_c_when_they_return_only_120_chars(monkeypatch):
    _mock_source_coverage(monkeypatch)
    calls = []
    initial_scripts = [
        _sized("热点反差", "甲", 720),
        _sized("用户痛点", "乙", 120),
        _sized("表达角度", "丙", 122),
    ]

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "variant_task" in payload:
            return _initial_variant(payload, initial_scripts)
        if "current_rewrites" in payload:
            return {
                "reviews": [
                    {
                        "index": index,
                        "audited_script": script,
                        "removed_unsupported_claims": [],
                        "unsupported_spans": [],
                        "unsupported_remaining": False,
                        "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
                    }
                    for index, script in enumerate(initial_scripts)
                ]
            }
        index = payload["variant"]["index"]
        return {
            "repaired_script": _sized(("用户痛点", "表达角度")[index - 1], ("乙", "丙")[index - 1], 710),
            "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
            "replacements": [],
            "unsupported_spans": [],
            "unsupported_remaining": False,
        }

    result = _run(monkeypatch, fake_generate)
    assert len([call for call in calls if "variant_task" in call]) == 3
    assert sorted(call["variant"]["index"] for call in calls if "current_script" in call) == [1, 2]
    assert result["diagnostic"]["actual_chars"] == [720, 710, 710]


def test_b_unsourced_yoy_and_consecutive_quarters_are_replaced_with_source_fact(monkeypatch):
    _mock_source_coverage(monkeypatch, patch_hard_facts=False)
    calls = []
    initial_scripts = [
        _sized("热点反差", "甲", 700),
        _sized("普通用户看到连续两个季度同比增长就下结论", "乙", 700),
        _sized("表达角度", "丙", 700),
    ]

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "variant_task" in payload:
            return _initial_variant(payload, initial_scripts)
        if "current_rewrites" in payload:
            return {
                "reviews": [
                    {
                        "index": index,
                        "audited_script": script,
                        "removed_unsupported_claims": [],
                        "unsupported_spans": (
                            [{"span": "连续两个季度同比增长", "reason": "来源未出现"}]
                            if index == 1
                            else []
                        ),
                        "unsupported_remaining": index == 1,
                        "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
                    }
                    for index, script in enumerate(initial_scripts)
                ]
            }
        assert payload["variant"]["index"] == 1
        assert {item["value"] for item in payload["hard_violations"]} >= {"连续两个季度", "同比"}
        return {
            "repaired_script": _sized("普通用户应核对资金用途时间边界和自身风险偏好", "乙", 710),
            "used_source_fact_ids": [*payload["used_source_fact_ids"], "ETF-03"],
            "replacements": [
                {
                    "unsupported_span": "连续两个季度同比增长",
                    "replacement_source_fact_id": "ETF-03",
                }
            ],
            "unsupported_spans": [],
            "unsupported_remaining": False,
        }

    result = _run(monkeypatch, fake_generate)
    repair = result["diagnostic"]["fact_fidelity"]["source_constrained_repairs"][0]
    assert repair["index"] == 1
    assert repair["replacements"][0]["replacement_source_fact_id"] == "ETF-03"
    assert result["diagnostic"]["fact_fidelity"]["hard_violations_after"] == [[], [], []]


def test_model_claiming_all_source_facts_does_not_clear_verified_unused_facts(monkeypatch):
    calls = []
    initial_scripts = [_sized(("反差", "痛点", "表达")[index], ("甲", "乙", "丙")[index], 650) for index in range(3)]

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "variant_task" in payload:
            return _initial_variant(payload, initial_scripts)
        if "current_rewrites" in payload:
            return {
                "reviews": [
                    {
                        "index": index,
                        "audited_script": script,
                        "removed_unsupported_claims": [],
                        "unsupported_spans": [],
                        "unsupported_remaining": False,
                        "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
                    }
                    for index, script in enumerate(initial_scripts)
                ]
            }
        assert payload["unused_source_fact_ids"]
        assert payload["used_source_fact_ids"] == []
        index = payload["variant"]["index"]
        return {
            "repaired_script": _sized(("反差", "痛点", "表达")[index], ("甲", "乙", "丙")[index], 690),
            "used_source_fact_ids": payload["used_source_fact_ids"],
            "replacements": [],
            "unsupported_spans": [],
            "unsupported_remaining": False,
        }

    result = _run(monkeypatch, fake_generate)
    assert result["generated_count"] == 1
    assert result["rewrites"][0]["provenance"] == "deterministic_scaffold"
    repair_calls = [call for call in calls if "current_script" in call]
    assert repair_calls
    assert all(call["unused_source_fact_ids"] for call in repair_calls)
    assert all(call["used_source_fact_ids"] == [] for call in repair_calls)


def test_no_progress_b_and_c_receive_one_final_source_reconstruction_each(monkeypatch):
    _mock_source_coverage(monkeypatch)
    calls = []
    initial_scripts = [
        _sized("热点反差", "甲", 747),
        _sized("用户痛点", "乙", 658),
        _sized("信息表达", "丙", 526),
    ]

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "variant_task" in payload:
            return _initial_variant(payload, initial_scripts)
        if "current_rewrites" in payload:
            return {
                "reviews": [
                    {
                        "index": index,
                        "audited_script": script,
                        "removed_unsupported_claims": [],
                        "unsupported_spans": [],
                        "unsupported_remaining": False,
                        "used_source_fact_ids": payload["source_fact_ledger"][
                            "fact_ids"
                        ],
                    }
                    for index, script in enumerate(initial_scripts)
                ]
            }
        if "current_script" in payload:
            index = payload["variant"]["index"]
            return {
                "repaired_script": initial_scripts[index],
                "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
                "replacements": [],
                "unsupported_spans": [],
                "unsupported_remaining": False,
            }
        index = payload["current_version"]["index"]
        return {
            "reconstructed_script": _sized(
                ("用户应逐项核对来源信号", "内容表达要区分事实条件和风险")[
                    index - 1
                ],
                ("乙", "丙")[index - 1],
                (710, 720)[index - 1],
            ),
            "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
            "unsupported_spans": [],
            "unsupported_remaining": False,
        }

    result = _run(monkeypatch, fake_generate)

    repair_calls = [call for call in calls if "current_script" in call]
    final_calls = [call for call in calls if "current_version" in call]
    assert [call["variant"]["index"] for call in repair_calls] == [1, 2]
    assert [call["current_version"]["index"] for call in final_calls] == [1, 2]
    assert all("corrected_transcript" in call for call in final_calls)
    assert all("source_fact_ledger" in call for call in final_calls)
    assert result["diagnostic"]["actual_chars"] == [747, 710, 720]
    assert result["diagnostic"]["llm_call_count"] == 8
    assert result["diagnostic"]["maximum_llm_calls"] == 9
    repairs = result["diagnostic"]["fact_fidelity"][
        "source_constrained_repairs"
    ]
    assert [item["outcome"] for item in repairs] == ["no_progress", "no_progress"]
    assert [
        item["index"]
        for item in result["diagnostic"]["fact_fidelity"][
            "final_source_reconstruction"
        ]
    ] == [1, 2]


def test_model_claimed_fact_ids_are_not_treated_as_direct_text_evidence():
    ledger = build_source_fact_ledger(FINANCE_FIXTURE)
    mapping = map_source_fact_coverage(
        ledger,
        "这是一段没有复述来源事实的普通口播。",
        claimed_fact_ids=ledger["fact_ids"],
    )
    assert mapping["directly_supported_fact_ids"] == []
    assert mapping["uncertain_fact_ids"] == ledger["fact_ids"]


def test_reusable_template_does_not_expose_many_ellipsis_placeholders():
    payload = _analysis([_sized("反差", "甲", 700)] * 3)
    payload["template"] = "先说……再说……然后……最后……"
    result = viral_analyzer.validate_viral_analysis_payload(payload, language="zh")
    assert result["template"] == "开头钩子 + 问题放大 + 信息价值 + 行动号召"
    assert "……" not in result["template"]


def test_source_scaffold_is_one_bounded_source_only_primary_fallback():
    ledger = build_source_fact_ledger(FINANCE_FIXTURE)
    scaffolds = [
        viral_analyzer._source_backed_scaffold(
            source_fact_ledger=ledger,
            index=index,
            minimum_chars=674,
            target_center_chars=749,
            maximum_chars=824,
        )
        for index in range(3)
    ]
    assert all(674 <= viral_analyzer._cjk_len(item) <= 824 for item in scaffolds)
    assert all(unsupported_hard_facts(FINANCE_FIXTURE, item) == [] for item in scaffolds)
    assert all(viral_analyzer._repeated_sentence_spans(item) == [] for item in scaffolds)
    assert len(set(scaffolds)) == 1
    assert "下面只按来源信息逐项核对" not in scaffolds[0]


def _natural_sized_script(marker: str, length: int) -> str:
    remaining = length
    sentences = []
    labels = ("第一部分", "第二部分", "第三部分", "第四部分", "第五部分", "第六部分", "第七部分", "第八部分", "第九部分")
    index = 0
    while remaining:
        chunk_length = min(90, remaining)
        label = labels[index % len(labels)]
        prefix = label[:chunk_length]
        sentences.append(prefix + marker * (chunk_length - viral_analyzer._cjk_len(prefix)) + "。")
        remaining -= chunk_length
        index += 1
    return "".join(sentences)


def _micro_gap_snapshot(*, gap=2, reasons=None, provenance="fact_review"):
    reasons = ["length"] if reasons is None else reasons
    return {
        "valid": False,
        "provenance": provenance,
        "exact_failure_reasons": reasons,
        "length_gap_direction": "below_minimum",
        "length_gap": gap,
        "hard_violations": ([{"category": "number", "value": "80%"}] if "hard_fact" in reasons else []),
        "coverage": {
            "unsupported_spans": ([{"span": "无来源片段"}] if "unsupported" in reasons else []),
            "used_count": 8,
        },
        "repeated_spans": (["重复句"] if "internal_repetition" in reasons else []),
        "incomplete_ending": "incomplete_ending" in reasons,
        "similarity_failure": "similarity" in reasons,
    }


@pytest.mark.parametrize(
    "snapshot",
    [
        _micro_gap_snapshot(gap=13),
        _micro_gap_snapshot(reasons=["length", "hard_fact"]),
        _micro_gap_snapshot(reasons=["length", "unsupported"]),
        _micro_gap_snapshot(reasons=["length", "incomplete_ending"]),
    ],
)
def test_micro_gap_rescue_rejects_non_length_only_candidates(snapshot):
    assert viral_analyzer._is_length_only_micro_gap_rescue_eligible(
        snapshot,
        minimum_fact_coverage_count=8,
        is_primary=True,
    ) is False


def test_neutral_micro_gap_closings_are_domain_safe():
    finance_closing = viral_analyzer._neutral_micro_gap_closing(
        industry="knowledge",
        raw_script=FINANCE_FIXTURE,
    )
    assert unsupported_hard_facts(FINANCE_FIXTURE, finance_closing) == []
    assert not any(char.isdigit() for char in finance_closing)
    emotional_closing = viral_analyzer._neutral_micro_gap_closing(
        industry="personal_brand",
        raw_script="先听听自己的感受。",
    )
    assert not any(term in emotional_closing for term in ("财经", "商业", "购买", "关注", "评论", "下单"))


def test_672_model_primary_is_rescued_without_primary_or_scaffold_call(monkeypatch):
    _mock_source_coverage(monkeypatch)
    calls = []
    reviewed_lengths = [401, 463, 672]

    async def fake_generate(_self, *, payload, **_kwargs):
        if "variant_task" in payload:
            calls.append(("initial", payload["variant_task"]["index"]))
            scripts = [
                _sized("反差", "甲", reviewed_lengths[0]),
                _sized("痛点", "乙", reviewed_lengths[1]),
                _sized("表达", "丙", reviewed_lengths[2]),
            ]
            return _initial_variant(payload, scripts)
        if "current_rewrites" in payload:
            calls.append(("review", None))
            return {
                "reviews": [
                    {
                        "index": index,
                        "audited_script": _sized(
                            ("反差", "痛点", "表达")[index],
                            ("甲", "乙", "丙")[index],
                            reviewed_lengths[index],
                        ),
                        "removed_unsupported_claims": [],
                        "unsupported_spans": [],
                        "unsupported_remaining": False,
                        "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
                    }
                    for index in range(3)
                ]
            }
        if "current_script" in payload and not payload.get("primary_convergence"):
            index = payload["variant"]["index"]
            calls.append(("optional", index))
            return {
                "repaired_script": _sized(("反差", "痛点")[index], ("甲", "乙")[index], 700),
                "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
                "replacements": [],
                "unsupported_spans": [],
                "unsupported_remaining": False,
            }
        raise AssertionError(f"unexpected call after micro-gap rescue: {sorted(payload)}")

    result = _run(monkeypatch, fake_generate)
    rescued = next(
        item
        for item in result["rewrites"]
        if item["provenance"] == "model_rewrite_with_neutral_closing"
    )
    assert 674 <= rescued["actual_chars"] <= 824
    assert rescued["script"].endswith("相关信息仍需持续核对。")
    assert result["diagnostic"]["primary_selection"]["selected_index"] == 2
    assert result["diagnostic"]["primary_selection"]["micro_gap_rescue"]["succeeded"] is True
    assert not any(stage in {"primary", "scaffold_polish"} for stage, _index in calls)
    assert result["fallback_generated_count"] == 0
    assert result["degraded_to_scaffold"] is False
    assert result["diagnostic"]["llm_call_count"] == 6
    assert result["diagnostic"]["llm_call_count"] <= 9
    for diagnostic in result["diagnostic"]["candidate_failure_diagnostics"]:
        assert "script" not in diagnostic
        assert "rewrite" not in diagnostic
        assert {
            "actual_chars",
            "length_gap",
            "hard_violations",
            "unsupported_spans",
            "fact_coverage",
            "incomplete_ending",
            "repeated_spans",
            "similarity_failure",
            "exact_failure_reasons",
            "provenance",
        } <= set(diagnostic)


def test_real_failure_shape_prioritizes_one_primary_before_optional_variants(monkeypatch):
    _mock_source_coverage(monkeypatch)
    calls = []
    primary_attempt = 0
    initial_lengths = [549, 449, 550]
    reviewed_lengths = [515, 459, 525]

    async def fake_generate(_self, *, payload, **_kwargs):
        nonlocal primary_attempt
        if "variant_task" in payload:
            calls.append(("initial", payload["variant_task"]["index"]))
            scripts = [
                _sized("反差", "甲", initial_lengths[0]),
                _sized("痛点", "乙", initial_lengths[1]),
                _sized("表达", "丙", initial_lengths[2]),
            ]
            return _initial_variant(payload, scripts)
        if "current_rewrites" in payload:
            calls.append(("review", None))
            return {
                "reviews": [
                    {
                        "index": index,
                        "audited_script": _sized(
                            ("反差", "痛点", "表达")[index],
                            ("甲", "乙", "丙")[index],
                            reviewed_lengths[index],
                        ),
                        "removed_unsupported_claims": [],
                        "unsupported_spans": [],
                        "unsupported_remaining": False,
                        "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
                    }
                    for index in range(3)
                ]
            }
        if payload.get("primary_convergence"):
            primary_attempt += 1
            calls.append(("primary", payload["variant"]["index"]))
            length = 574 if primary_attempt == 1 else 780
            return {
                "title": "收敛主稿",
                "script": _sized("表达", "丙", length),
                "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
            }
        if "current_script" in payload:
            index = payload["variant"]["index"]
            calls.append(("optional", index))
            return {
                "repaired_script": _sized(("反差", "痛点")[index], ("甲", "乙")[index], 700),
                "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
                "replacements": [],
                "unsupported_spans": [],
                "unsupported_remaining": False,
            }
        raise AssertionError(f"unexpected payload keys: {sorted(payload)}")

    result = _run(monkeypatch, fake_generate)
    assert result["diagnostic"]["primary_selection"]["selected_index"] == 2
    assert result["diagnostic"]["primary_selection"]["attempts"][0]["actual_chars"] == 574
    assert result["diagnostic"]["primary_selection"]["attempts"][1]["actual_chars"] == 780
    review_position = calls.index(("review", None))
    assert calls[review_position + 1 : review_position + 3] == [("primary", 2), ("primary", 2)]
    assert all(stage != "optional" for stage, _index in calls[: review_position + 3])
    assert result["diagnostic"]["llm_call_count"] <= 9
    assert result["diagnostic"]["scaffold_polish"]["attempted"] is False
    assert result["model_rewrite_succeeded"] is True


@pytest.mark.parametrize("polish_succeeds", [True, False])
def test_real_failure_shape_reserves_scaffold_polish_and_reports_fallback(monkeypatch, polish_succeeds):
    _mock_source_coverage(monkeypatch)
    calls = []
    polish_payloads = []
    initial_lengths = [549, 449, 550]
    reviewed_lengths = [515, 459, 525]

    async def fake_generate(_self, *, payload, **_kwargs):
        if "variant_task" in payload:
            calls.append(("initial", payload["variant_task"]["index"]))
            scripts = [
                _sized("反差", "甲", initial_lengths[0]),
                _sized("痛点", "乙", initial_lengths[1]),
                _sized("表达", "丙", initial_lengths[2]),
            ]
            return _initial_variant(payload, scripts)
        if "current_rewrites" in payload:
            calls.append(("review", None))
            return {
                "reviews": [
                    {
                        "index": index,
                        "audited_script": _sized(
                            ("反差", "痛点", "表达")[index],
                            ("甲", "乙", "丙")[index],
                            reviewed_lengths[index],
                        ),
                        "removed_unsupported_claims": [],
                        "unsupported_spans": [],
                        "unsupported_remaining": False,
                        "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
                    }
                    for index in range(3)
                ]
            }
        if payload.get("primary_convergence"):
            calls.append(("primary", payload["variant"]["index"]))
            return {
                "title": "仍然偏短",
                "script": _sized("表达", "丙", 574),
                "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
            }
        if payload.get("scaffold_polish"):
            calls.append(("scaffold_polish", None))
            polish_payloads.append(payload)
            length = 780 if polish_succeeds else 500
            return {
                "title": "来源事实AI润色稿",
                "script": _natural_sized_script("甲", length),
                "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"][:8],
            }
        raise AssertionError(f"B/C must not consume a call before primary fallback: {sorted(payload)}")

    result = _run(monkeypatch, fake_generate)
    assert [stage for stage, _index in calls].count("primary") == 2
    assert calls[-1] == ("scaffold_polish", None)
    assert len(polish_payloads) == (1 if polish_succeeds else 2)
    assert result["diagnostic"]["llm_call_count"] == (7 if polish_succeeds else 8)
    assert result["diagnostic"]["llm_call_count"] <= 9
    assert result["generated_count"] == 1
    assert result["filtered_duplicate_count"] + result["filtered_invalid_count"] == 2
    assert result["filtered_invalid_count"] == 2
    assert result["model_invalid_count"] == 3
    assert result["fallback_generated_count"] == 1
    assert result["degraded_to_scaffold"] is True
    assert result["model_rewrite_succeeded"] is False
    assert result["rewrites"][0]["fact_fidelity"]["hard_violations"] == []
    if polish_succeeds:
        assert result["provenance"] == "scaffold_polished_by_model"
        assert 674 <= result["rewrites"][0]["actual_chars"] <= 824
        assert "\n\n" in result["rewrites"][0]["script"]
        assert "\n" not in result["rewrites"][0]["script"].replace("\n\n", "")
        assert result["degradation_reason"] == "独立改写版本未通过校验，当前展示基于来源事实的AI润色稿。"
    else:
        assert polish_payloads[1]["scaffold_polish_retry"] is True
        assert polish_payloads[1]["previous_failure"]["actual_chars"] == 500
        assert polish_payloads[1]["previous_failure"]["exact_failure_reasons"] == ["length"]
        assert result["provenance"] == "deterministic_scaffold"
        assert result["degradation_reason"] == (
            "AI改写版本未通过质量校验，当前展示来源保底整理稿。"
            "内容基于原转写，事实安全，但改写程度有限。"
        )


def test_parallel_initial_generation_exception_is_controlled(monkeypatch):
    async def fake_generate(_self, *, payload, **_kwargs):
        if payload["variant_task"]["index"] == 1:
            raise RuntimeError("provider limit")
        return _initial_variant(payload, [_sized("甲", "甲", 700)] * 3)

    result = _run(monkeypatch, fake_generate)
    assert result["generated_count"] == 1
    assert result["diagnostic"]["version_states"][1]["state"] == "failed"
    assert result["diagnostic"]["version_states"][1]["error_code"] == "unexpected_provider_error"


def test_missing_independent_rewrite_json_field_is_controlled(monkeypatch):
    _mock_source_coverage(monkeypatch)
    calls = [0, 0, 0]

    async def fake_generate(_self, *, payload, **_kwargs):
        index = payload["variant_task"]["index"]
        calls[index] += 1
        if index == 2:
            return {"rewrite": {"title": "版本C"}}
        scripts = [_sized("甲", "甲", 700), _sized("乙", "乙", 700), _sized("丙", "丙", 700)]
        return _initial_variant(payload, scripts)

    result = _run(monkeypatch, fake_generate)
    assert calls == [1, 1, 2]
    assert result["diagnostic"]["version_states"][2]["error_code"] == "llm_json_missing_fields"
    assert result["diagnostic"]["llm_call_count"] == 4
    assert result["generated_count"] >= 1


def _successful_review(payload):
    return {
        "reviews": [
            {
                "index": item["index"],
                "audited_script": item["script"],
                "removed_unsupported_claims": [],
                "unsupported_spans": [],
                "unsupported_remaining": False,
                "used_source_fact_ids": payload["source_fact_ledger"]["fact_ids"],
            }
            for item in payload["current_rewrites"]
        ]
    }


def test_b_connection_failure_retries_only_b_and_never_exceeds_concurrency_limit(monkeypatch):
    calls = [0, 0, 0]
    active = 0
    maximum_active = 0
    scripts = [_sized("反差", "甲", 700), _sized("痛点", "乙", 710), _sized("表达", "丙", 720)]

    async def fake_generate(_self, *, payload, **_kwargs):
        nonlocal active, maximum_active
        if "variant_task" not in payload:
            return _successful_review(payload)
        index = payload["variant_task"]["index"]
        calls[index] += 1
        active += 1
        maximum_active = max(maximum_active, active)
        try:
            await asyncio.sleep(0.01)
            if index == 1 and calls[index] == 1:
                raise LLMProviderError(
                    code="llm_network_error",
                    message="connection reset",
                    retryable=True,
                )
            return _initial_variant(payload, scripts)
        finally:
            active -= 1

    monkeypatch.setattr(viral_analyzer, "SOURCE_RETRY_BASE_DELAY_SECONDS", 0)
    monkeypatch.setattr(viral_analyzer, "SOURCE_RETRY_JITTER_SECONDS", 0)
    result = _run(monkeypatch, fake_generate)

    assert calls == [1, 2, 1]
    assert maximum_active == 2
    assert result["diagnostic"]["maximum_observed_concurrency"] == 2
    assert [len(item["attempts"]) for item in result["diagnostic"]["version_states"]] == [1, 2, 1]
    assert all(item["state"] == "succeeded" for item in result["diagnostic"]["version_states"])


@pytest.mark.parametrize(
    ("code", "http_status"),
    [
        ("llm_timeout", None),
        ("llm_network_error", None),
        ("llm_rate_limited", 429),
        ("llm_upstream_timeout", 504),
        ("llm_http_error", 503),
    ],
)
def test_retryable_provider_failures_use_local_retry(monkeypatch, code, http_status):
    calls = [0, 0, 0]
    scripts = [_sized("反差", "甲", 700), _sized("痛点", "乙", 710), _sized("表达", "丙", 720)]

    async def fake_generate(_self, *, payload, **_kwargs):
        if "variant_task" not in payload:
            return _successful_review(payload)
        index = payload["variant_task"]["index"]
        calls[index] += 1
        if index == 1 and calls[index] == 1:
            raise LLMProviderError(
                code=code,
                message="transient",
                retryable=True,
                http_status=http_status,
            )
        return _initial_variant(payload, scripts)

    monkeypatch.setattr(viral_analyzer, "SOURCE_RETRY_BASE_DELAY_SECONDS", 0)
    monkeypatch.setattr(viral_analyzer, "SOURCE_RETRY_JITTER_SECONDS", 0)
    result = _run(monkeypatch, fake_generate)
    assert calls == [1, 2, 1]
    b_attempts = result["diagnostic"]["version_states"][1]["attempts"]
    assert [item["state"] for item in b_attempts] == ["failed", "succeeded"]
    assert b_attempts[0]["error_code"] == code


def test_local_retry_uses_exponential_delay_with_jitter(monkeypatch):
    calls = [0, 0, 0]
    sleeps = []
    scripts = [_sized("反差", "甲", 700), _sized("痛点", "乙", 710), _sized("表达", "丙", 720)]

    async def fake_sleep(delay):
        sleeps.append(delay)

    async def fake_generate(_self, *, payload, **_kwargs):
        if "variant_task" not in payload:
            return _successful_review(payload)
        index = payload["variant_task"]["index"]
        calls[index] += 1
        if index == 1 and calls[index] == 1:
            raise LLMProviderError(
                code="llm_rate_limited",
                message="rate limited",
                retryable=True,
                http_status=429,
            )
        return _initial_variant(payload, scripts)

    monkeypatch.setattr(viral_analyzer.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(viral_analyzer.random, "uniform", lambda _low, _high: 0.05)
    monkeypatch.setattr(viral_analyzer, "SOURCE_RETRY_BASE_DELAY_SECONDS", 0.1)
    monkeypatch.setattr(viral_analyzer, "SOURCE_RETRY_JITTER_SECONDS", 0.1)
    _run(monkeypatch, fake_generate)
    assert calls == [1, 2, 1]
    assert sleeps == [pytest.approx(0.15)]


def test_truncated_or_contract_failure_does_not_retry_and_preserves_other_successes(monkeypatch):
    calls = [0, 0, 0]
    scripts = [_sized("反差", "甲", 700), _sized("痛点", "乙", 710), _sized("表达", "丙", 720)]

    async def fake_generate(_self, *, payload, **_kwargs):
        index = payload["variant_task"]["index"]
        calls[index] += 1
        if index == 1:
            raise LLMProviderError(
                code="llm_response_truncated",
                message="finish_reason=length",
                retryable=True,
                http_status=200,
            )
        return _initial_variant(payload, scripts)

    result = _run(monkeypatch, fake_generate)
    assert calls == [1, 1, 1]
    assert [item["state"] for item in result["diagnostic"]["version_states"]] == ["succeeded", "failed", "succeeded"]
    assert result["diagnostic"]["version_states"][1]["error_code"] == "llm_response_truncated"
    assert result["generated_count"] >= 1


def test_empty_content_exhaustion_compactly_regenerates_only_failed_b(monkeypatch):
    _mock_source_coverage(monkeypatch)
    calls = [0, 0, 0]
    observed = []
    scripts = [_sized("反差", "甲", 700), _sized("痛点", "乙", 710), _sized("表达", "丙", 720)]

    async def fake_generate(_self, *, payload, system, **kwargs):
        if "variant_task" not in payload:
            return _successful_review(payload)
        index = payload["variant_task"]["index"]
        calls[index] += 1
        observed.append((index, calls[index], payload, system, kwargs))
        if index == 1 and calls[index] == 1:
            raise LLMProviderError(
                code="llm_empty_content_exhausted",
                message="finish_reason=length;content=empty",
                retryable=True,
                http_status=200,
                content_length=0,
                reasoning_content_length=32000,
                completion_tokens=8000,
            )
        return _initial_variant(payload, scripts)

    result = _run(monkeypatch, fake_generate)

    assert calls == [1, 2, 1]
    b_calls = [item for item in observed if item[0] == 1]
    assert [item[1] for item in b_calls] == [1, 2]
    compact_payload, compact_system, compact_kwargs = b_calls[1][2], b_calls[1][3], b_calls[1][4]
    assert set(compact_payload["schema"]) == {"rewrite"}
    assert "analysis" not in compact_payload["schema"]
    assert "只输出最终 JSON" in compact_system
    assert all("不输出分析" in item or "JSON" in item or "script" in item or "事实" in item or "字符" in item or "角度" in item for item in compact_payload["requirements"])
    assert compact_kwargs["attempt_label"] == "variant_1_compact_regeneration"
    assert compact_kwargs["thinking_mode"] == "disabled"
    b_state = result["diagnostic"]["version_states"][1]
    assert b_state["compact_regenerations"] == 1
    assert [item["mode"] for item in b_state["attempts"]] == ["initial", "compact_regeneration"]
    assert result["diagnostic"]["llm_call_count"] == 5


@pytest.mark.parametrize("failure_code", ["llm_empty_content", "llm_json_parse_error"])
def test_output_contract_failure_compactly_regenerates_only_failed_a(monkeypatch, failure_code):
    calls = [0, 0, 0]
    observed = []
    scripts = [_sized("反差", "甲", 700), _sized("痛点", "乙", 710), _sized("表达", "丙", 720)]

    async def fake_generate(_self, *, payload, system, **kwargs):
        if "variant_task" not in payload:
            return _successful_review(payload)
        index = payload["variant_task"]["index"]
        calls[index] += 1
        observed.append((index, payload, system, kwargs))
        if index == 0 and calls[index] == 1:
            raise LLMProviderError(
                code=failure_code,
                message="invalid output",
                retryable=False,
                http_status=200,
                content_length=0 if failure_code == "llm_empty_content" else 2774,
                finish_reason="stop",
                content_type="null" if failure_code == "llm_empty_content" else "str",
                parser_repair_applied=failure_code == "llm_json_parse_error",
            )
        return _initial_variant(payload, scripts)

    result = _run(monkeypatch, fake_generate)

    assert calls == [2, 1, 1]
    compact = [item for item in observed if item[0] == 0][1]
    assert set(compact[1]) >= {"content_input", "source_fact_ledger", "variant_task", "length_target", "schema"}
    assert set(compact[1]["schema"]) == {"rewrite"}
    assert "只输出最终 JSON" in compact[2]
    assert compact[3]["attempt_label"] == "variant_0_compact_regeneration"
    assert compact[3]["thinking_mode"] == "disabled"
    assert result["diagnostic"]["version_states"][0]["compact_regenerations"] == 1
    assert result["diagnostic"]["llm_call_count"] <= 9


def test_missing_script_compactly_regenerates_only_failed_b(monkeypatch):
    calls = [0, 0, 0]
    scripts = [_sized("反差", "甲", 700), _sized("痛点", "乙", 710), _sized("表达", "丙", 720)]

    async def fake_generate(_self, *, payload, **_kwargs):
        if "variant_task" not in payload:
            return _successful_review(payload)
        index = payload["variant_task"]["index"]
        calls[index] += 1
        if index == 1 and calls[index] == 1:
            return {"rewrite": {"title": "版本B"}}
        return _initial_variant(payload, scripts)

    result = _run(monkeypatch, fake_generate)

    assert calls == [1, 2, 1]
    b_state = result["diagnostic"]["version_states"][1]
    assert b_state["retry_reason"] == "llm_json_missing_fields"
    assert b_state["attempts"][0]["error_code"] == "llm_json_missing_fields"


def test_second_json_parse_failure_stops_without_third_generation(monkeypatch):
    _mock_source_coverage(monkeypatch)
    calls = [0, 0, 0]
    scripts = [_sized("反差", "甲", 700), _sized("痛点", "乙", 710), _sized("表达", "丙", 720)]

    async def fake_generate(_self, *, payload, **_kwargs):
        index = payload["variant_task"]["index"]
        calls[index] += 1
        if index == 0:
            raise LLMProviderError(
                code="llm_json_parse_error",
                message="invalid json",
                retryable=False,
                http_status=200,
                content_length=2774,
                finish_reason="stop",
                content_type="str",
                parser_repair_applied=True,
            )
        return _initial_variant(payload, scripts)

    result = _run(monkeypatch, fake_generate)
    assert calls == [2, 1, 1]
    assert result["diagnostic"]["version_states"][0]["error_code"] == "llm_json_parse_error"
    assert result["diagnostic"]["llm_call_count"] == 4
    assert result["diagnostic"]["maximum_llm_calls"] == 9


def test_second_empty_content_is_marked_exhausted_without_third_generation(monkeypatch):
    _mock_source_coverage(monkeypatch)
    calls = [0, 0, 0]
    scripts = [_sized("反差", "甲", 700), _sized("痛点", "乙", 710), _sized("表达", "丙", 720)]

    async def fake_generate(_self, *, payload, **_kwargs):
        index = payload["variant_task"]["index"]
        calls[index] += 1
        if index == 1:
            raise LLMProviderError(
                code="llm_empty_content",
                message="content=empty",
                retryable=True,
                http_status=200,
                content_length=0,
                reasoning_content_length=32000,
                completion_tokens=8000,
            )
        return _initial_variant(payload, scripts)

    result = _run(monkeypatch, fake_generate)
    assert calls == [1, 2, 1]
    b_state = result["diagnostic"]["version_states"][1]
    assert b_state["compact_regenerations"] == 1
    assert [item["mode"] for item in b_state["attempts"]] == ["initial", "compact_regeneration"]
    assert result["diagnostic"]["llm_call_count"] == 4
    assert result["diagnostic"]["maximum_llm_calls"] == 9


def test_request_level_llm_call_budget_is_strict(monkeypatch):
    calls = [0, 0, 0]
    provider_calls = 0
    scripts = [_sized("反差", "甲", 700), _sized("痛点", "乙", 710), _sized("表达", "丙", 720)]

    async def fake_generate(_self, *, payload, **_kwargs):
        nonlocal provider_calls
        provider_calls += 1
        if "variant_task" in payload:
            index = payload["variant_task"]["index"]
            calls[index] += 1
            if calls[index] == 1:
                raise LLMProviderError(
                    code="llm_network_error",
                    message="transient",
                    retryable=True,
                )
            return _initial_variant(payload, scripts)
        if "current_rewrites" in payload:
            review = _successful_review(payload)
            for item in review["reviews"]:
                item["audited_script"] = _sized("不足", "丁", 650)
            return review
        if "current_script" in payload:
            index = payload["variant"]["index"]
            return {
                "repaired_script": _sized("不足", "丁", 650),
                "used_source_fact_ids": [],
                "replacements": [],
                "unsupported_spans": [],
                "unsupported_remaining": False,
            }
        raise AssertionError("provider must not be called after budget exhaustion")

    monkeypatch.setattr(viral_analyzer, "SOURCE_RETRY_BASE_DELAY_SECONDS", 0)
    monkeypatch.setattr(viral_analyzer, "SOURCE_RETRY_JITTER_SECONDS", 0)
    result = _run(monkeypatch, fake_generate)
    assert calls == [2, 2, 2]
    assert provider_calls == viral_analyzer.MAX_SOURCE_CONSTRAINED_LLM_CALLS
    assert result["diagnostic"]["llm_call_count"] == viral_analyzer.MAX_SOURCE_CONSTRAINED_LLM_CALLS
    assert result["diagnostic"]["maximum_llm_calls"] == viral_analyzer.MAX_SOURCE_CONSTRAINED_LLM_CALLS
    assert result["diagnostic"]["fact_fidelity"]["final_source_reconstruction"] == []
    assert result["diagnostic"]["primary_selection"]["attempts"][-1]["outcome"] == (
        "reserved_for_scaffold_polish"
    )
    assert result["diagnostic"]["scaffold_polish"]["attempted"] is True
    assert result["generated_count"] == 1
    assert result["rewrites"][0]["provenance"] == "deterministic_scaffold"
