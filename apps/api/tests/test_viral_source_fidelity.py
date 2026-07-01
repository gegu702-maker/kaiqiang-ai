import re

from app.services.viral_pipeline import REWRITE_TITLES, _fallback_rewrites, _normalize_rewrites


CTA_PATTERNS = (
    re.compile(r"评论区说说你的判断"),
    re.compile(r"把这个拆法先记下来，下一次热点就能直接套用"),
    re.compile(r"后面如果产业链继续有新变化，我会再单独拆给你看"),
)

HARD_PHRASES = ("行动号召", "信息价值", "模板说明", "真正")


SPACEX_TRANSCRIPT = (
    "最近很多人只盯着 SpaceX 要不要上市、会不会登陆纳斯达克的传闻，"
    "但原视频真正想讲的不是真假消息本身。"
    "它继续往下拆：如果 SpaceX 未来资本化，供应链会先承压，关键材料、发动机和卫星制造的技术量产都会被放大。"
    "这里还牵涉地缘政治和出口限制，所以风险不只是公司估值，而是产业链谁能供货、谁能替代、谁能拿到新机会。"
)


def _spacex_analysis():
    return {
        "topic": "SpaceX 上市传闻",
        "hook": "表面看是 SpaceX 上市消息，往下看其实是供应链风险和产业链机会。",
        "selling_points": ["上市传闻", "供应链风险", "关键材料", "产业链机会"],
        "structure": ["核心事件", "供应链矛盾", "关键材料", "技术量产", "地缘政治", "产业链机会"],
        "template": "先讲 SpaceX 上市传闻，再讲供应链风险，最后讲关键材料、技术量产、地缘政治和产业链机会。",
        "source_video_core": {
            "core_event": "SpaceX 上市和纳斯达克传闻",
            "core_conflict": "表面是上市消息，背后是供应链风险、关键材料和技术量产的不确定性",
            "key_entities": ["SpaceX", "纳斯达克", "供应链", "关键材料", "技术量产", "地缘政治", "产业链"],
            "causal_chain": "如果 SpaceX 资本化预期升温，供应链、关键材料和技术量产压力会被放大",
            "business_implication": "产业链里能供货、能替代、能突破材料和量产限制的公司可能出现新机会",
            "audience_takeaway": "别只看上市传闻真假，要看供应链风险和产业链机会",
        },
    }


def _cta_count(script: str) -> int:
    return sum(len(pattern.findall(script)) for pattern in CTA_PATTERNS)


def _assert_clean_spoken_script(script: str) -> None:
    for phrase in HARD_PHRASES:
        assert phrase not in script
    assert _cta_count(script) <= 1
    assert "互动你觉得" not in script
    assert "判断 我更想提醒" not in script


def _assert_spacex_core_present(script: str) -> None:
    assert "SpaceX" in script
    assert any(term in script for term in ("上市", "纳斯达克", "传闻", "消息"))
    assert any(term in script for term in ("供应链", "产业链"))
    assert any(term in script for term in ("风险", "机会"))
    assert any(term in script for term in ("关键材料", "技术量产", "地缘政治"))


def test_spacex_fallback_rewrites_preserve_source_video_core():
    rewrites = _fallback_rewrites(_spacex_analysis(), SPACEX_TRANSCRIPT)

    assert [item["title"] for item in rewrites] == REWRITE_TITLES
    assert len(rewrites) == 3
    for item in rewrites:
        script = item["script"]
        _assert_clean_spoken_script(script)
        _assert_spacex_core_present(script)

    version_a = rewrites[0]["script"]
    assert "标题党" not in version_a
    assert not ("假消息" in version_a and "供应链" not in version_a)

    version_c = rewrites[2]["script"]
    assert any(term in version_c for term in ("商业", "机会", "产业链", "供应链"))


def test_spacex_normalize_rewrites_replaces_surface_level_scripts():
    rewrites = _normalize_rewrites(
        [
            {"title": "版本A：热点反差版", "script": "这可能是假消息，大家不要被标题党骗了，招股书没有出来之前都不用管。"},
            {"title": "版本B：用户痛点版", "script": "很多人只看标题就跟风，这样容易误判热点。"},
            {"title": "版本C：商业机会版", "script": "这个消息有热度，适合做一条商业口播。"},
        ],
        _spacex_analysis(),
        SPACEX_TRANSCRIPT,
    )

    assert [item["title"] for item in rewrites] == REWRITE_TITLES
    assert len(rewrites) == 3
    for item in rewrites:
        script = item["script"]
        _assert_clean_spoken_script(script)
        _assert_spacex_core_present(script)

    assert "标题党" not in rewrites[0]["script"]
    assert any(term in rewrites[2]["script"] for term in ("产业链", "供应链", "关键材料", "技术量产"))
