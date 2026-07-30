import asyncio

import pytest
from fastapi import HTTPException

from app.services import viral_analyzer
from app.services.viral_fact_fidelity import (
    build_source_fact_ledger,
    unsupported_hard_facts,
)
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
    ledger = build_source_fact_ledger(FINANCE_FIXTURE)
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
        "反差在于机构表达信心不等于短期涨跌承诺。" + "核对公告经营数据资金流向并保留风险边界。" * 36,
        "普通用户的痛点是容易把机构动作当成自己的投资结论。" + "判断回购仍要核对资金来源公司基本面和执行节奏。" * 30,
        "观察机会时要把保险回购机构自购中报和外资观点分别验证。" + "这些信号仍然不是确定性买入信号。" * 44,
    ]

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "source_fact_ledger" not in payload:
            return _analysis(bad_scripts)
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
                    "unsupported_remaining": False,
                }
                for index, script in enumerate(clean_scripts)
            ]
        }

    result = _run(monkeypatch, fake_generate)
    assert len(calls) == 2
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
        if "source_fact_ledger" not in payload:
            return _analysis(scripts)
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
                    "unsupported_remaining": False,
                }
                for index in range(3)
            ]
        }

    with pytest.raises(HTTPException) as raised:
        _run(monkeypatch, fake_generate)
    detail = raised.value.detail
    assert detail["code"] == "analysis_fact_fidelity_failed"
    assert detail["stage"] == "fact_review"
    assert {
        (item["category"], item["value"])
        for item in detail["fact_fidelity"]["hard_violations_after"][0]
    } == {
        ("indicator_or_specific_fact", "股价慢慢修复"),
        ("unsourced_entity", "某公司"),
    }
