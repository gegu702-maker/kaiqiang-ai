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

    with pytest.raises(HTTPException) as raised:
        _run(monkeypatch, fake_generate)
    detail = raised.value.detail
    assert detail["code"] == "analysis_fact_fidelity_failed"
    assert detail["stage"] == "source_constrained_repair"
    assert {
        (item["category"], item["value"])
        for item in detail["fact_fidelity"]["hard_violations_after"][0]
    } == {
        ("indicator_or_specific_fact", "股价慢慢修复"),
        ("unsourced_entity", "某公司"),
    }


def test_source_constrained_repair_restores_range_after_fact_review_is_short(monkeypatch):
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
    assert result["diagnostic"]["actual_chars"] == [690, 690, 690]
    assert all(
        item["coverage_rate"] < 1.0
        for item in result["diagnostic"]["source_fact_coverage"]
    )
    assert all(
        item["unused_source_fact_ids"]
        for item in result["diagnostic"]["source_fact_coverage"]
    )


def test_no_progress_b_and_c_receive_one_final_source_reconstruction_each(monkeypatch):
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


def test_source_scaffold_is_bounded_source_backed_and_distinct():
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
    assert max(
        viral_analyzer.rewrite_similarity(scaffolds[left], scaffolds[right])
        for left in range(3)
        for right in range(left + 1, 3)
    ) < 0.75


def test_parallel_initial_generation_exception_is_controlled(monkeypatch):
    async def fake_generate(_self, *, payload, **_kwargs):
        if payload["variant_task"]["index"] == 1:
            raise RuntimeError("provider limit")
        return _initial_variant(payload, [_sized("甲", "甲", 700)] * 3)

    with pytest.raises(HTTPException) as raised:
        _run(monkeypatch, fake_generate)
    detail = raised.value.detail
    assert detail["code"] == "analysis_independent_generation_failed"
    assert detail["stage"] == "independent_initial"
    assert detail["failed_versions"] == [
        {
            "index": 1,
            "error_type": "RuntimeError",
            "error_code": "unexpected_provider_error",
            "retryable": False,
        }
    ]


def test_missing_independent_rewrite_json_field_is_controlled(monkeypatch):
    async def fake_generate(_self, *, payload, **_kwargs):
        if payload["variant_task"]["index"] == 2:
            return {"rewrite": {"title": "版本C"}}
        scripts = [_sized("甲", "甲", 700), _sized("乙", "乙", 700), _sized("丙", "丙", 700)]
        return _initial_variant(payload, scripts)

    with pytest.raises(HTTPException) as raised:
        _run(monkeypatch, fake_generate)
    detail = raised.value.detail
    assert detail["code"] == "analysis_independent_generation_failed"
    assert detail["failed_versions"] == [{"index": 2, "error_type": "missing_rewrite_script"}]


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

    with pytest.raises(HTTPException) as raised:
        _run(monkeypatch, fake_generate)
    detail = raised.value.detail
    assert calls == [1, 1, 1]
    assert detail["retryable"] is False
    assert detail["succeeded_versions"] == [0, 2]
    assert [item["state"] for item in detail["version_states"]] == ["succeeded", "failed", "succeeded"]
    assert detail["failed_versions"][0]["error_code"] == "llm_response_truncated"


def test_empty_content_exhaustion_compactly_regenerates_only_failed_b(monkeypatch):
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


def test_second_empty_content_exhaustion_fails_without_third_generation(monkeypatch):
    calls = [0, 0, 0]
    scripts = [_sized("反差", "甲", 700), _sized("痛点", "乙", 710), _sized("表达", "丙", 720)]

    async def fake_generate(_self, *, payload, **_kwargs):
        index = payload["variant_task"]["index"]
        calls[index] += 1
        if index == 1:
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

    with pytest.raises(HTTPException) as raised:
        _run(monkeypatch, fake_generate)

    detail = raised.value.detail
    assert calls == [1, 2, 1]
    assert detail["retryable"] is False
    assert detail["succeeded_versions"] == [0, 2]
    assert detail["failed_versions"][0]["error_code"] == "llm_empty_content_exhausted"
    b_state = detail["version_states"][1]
    assert b_state["compact_regenerations"] == 1
    assert [item["mode"] for item in b_state["attempts"]] == ["initial", "compact_regeneration"]
    assert detail["llm_call_count"] == 4
    assert detail["maximum_llm_calls"] == 9


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
    assert all(
        item["outcome"] == "source_scaffold"
        for item in result["diagnostic"]["fact_fidelity"][
            "final_source_reconstruction"
        ]
    )
