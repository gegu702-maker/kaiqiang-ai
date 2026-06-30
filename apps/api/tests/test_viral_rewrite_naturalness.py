import re

from app.services.viral_analyzer import smooth_spoken_script
from app.services.viral_pipeline import REWRITE_TITLES, _fallback_rewrites, _normalize_rewrites


CTA_PATTERNS = (
    re.compile(r"评论区说说你的判断"),
    re.compile(r"把这个拆法先记下来，下一次热点就能直接套用"),
    re.compile(r"后面如果产业链继续有新变化，我会再单独拆给你看"),
)

HARD_PHRASES = (
    "真正",
    "行动号召",
    "信息价值",
    "模板说明",
    "可复用模板",
    "结构",
    "值得学习的是",
    "先别急着模仿表面内容",
)


def _sample_analysis():
    return {
        "topic": "AI 玩具出海",
        "hook": "一个看似小众的玩具赛道，正在被 AI 重新放大。",
        "selling_points": ["热点反差", "用户痛点", "商业机会", "内容选题"],
        "structure": ["开头钩子", "问题放大", "信息增量", "商业判断", "互动收尾"],
        "template": "开头反差 + 用户问题 + 商业判断 + 互动收尾",
    }


def _cta_count(script: str) -> int:
    return sum(len(pattern.findall(script)) for pattern in CTA_PATTERNS)


def test_pipeline_fallback_keeps_three_named_versions_and_natural_scripts():
    rewrites = _fallback_rewrites(_sample_analysis(), "AI 玩具公司正在加速出海，海外家长关注陪伴和教育场景。")

    assert [item["title"] for item in rewrites] == REWRITE_TITLES
    assert len(rewrites) == 3
    for item in rewrites:
        script = item["script"]
        assert len(script) >= 80
        for phrase in HARD_PHRASES:
            assert phrase not in script
        assert "这个版本适合" not in script
        assert _cta_count(script) <= 1
        assert "互动你觉得" not in script
        assert "判断 我更想提醒" not in script

    version_a = rewrites[0]["script"]
    assert version_a.count("评论区说说你的判断") <= 1
    assert version_a.count("我更想提醒") <= 1
    assert "你觉得的重点" not in version_a
    assert "开头有反差，中间有问题，结尾有互动" not in version_a


def test_normalize_rewrites_polishes_llm_scripts_without_changing_count():
    rewrites = _normalize_rewrites(
        [
            {"title": "版本A：热点反差版", "script": "文案：真正值得关注的不是表面的热闹，而是AI玩具出海背后的需求变化。"},
            {"title": "版本B：用户痛点版", "script": "如果你做内容，先讲用户痛点，再补充信息价值，最后行动号召。"},
            {"title": "版本C：商业机会版", "script": "这个版本适合老板看，可复用模板是产业链机会分析。"},
        ],
        _sample_analysis(),
        "AI 玩具公司正在加速出海，海外家长关注陪伴和教育场景。",
    )

    assert [item["title"] for item in rewrites] == REWRITE_TITLES
    assert len(rewrites) == 3
    joined = "\n".join(item["script"] for item in rewrites)
    assert "文案：" not in joined
    for phrase in HARD_PHRASES:
        assert phrase not in joined
    for item in rewrites:
        assert _cta_count(item["script"]) <= 1
        assert "互动你觉得" not in item["script"]
        assert "评论区说说你的判断 我更想提醒" not in item["script"]


def test_smooth_spoken_script_removes_mechanical_phrasing():
    script = "口播文案：真正值得关注的不是表面的热闹，真正要看的，是背后的信息价值和行动号召。"

    polished = smooth_spoken_script(script)

    assert not polished.startswith("口播文案")
    assert "真正值得关注的不是表面的热闹" not in polished
    assert "真正要看的，是" not in polished
    assert "信息价值" not in polished
    assert "行动号召" not in polished
    assert "真正" not in polished


def test_smooth_spoken_script_repairs_bad_sentence_joins():
    script = "开头有反差，中间有问题，结尾有互动你觉得真正的重点在哪里？评论区说说你的判断 我更想提醒你看一个反差。"

    polished = smooth_spoken_script(script)

    assert "互动你觉得" not in polished
    assert "判断 我更想提醒" not in polished
    assert "真正" not in polished
    assert "你觉得的重点" not in smooth_spoken_script("你觉得真正的重点在哪里？")
