import re

from app.services.viral_pipeline import REWRITE_TITLES, _fallback_rewrites, _normalize_rewrites


CTA_PATTERNS = (
    re.compile(r"评论区说说你的判断"),
    re.compile(r"把这个拆法先记下来，下一次热点就能直接套用"),
    re.compile(r"后面如果这个方向继续有新变化，我会再单独拆给你看"),
)

SYSTEM_OR_HARD_PHRASES = (
    "原视频",
    "这个视频",
    "视频里",
    "这条视频",
    "原文",
    "素材",
    "主线是",
    "想提醒的是",
    "→",
    "行动号召",
    "信息价值",
    "模板说明",
    "真正",
)
SUPPLY_CHAIN_PHRASES = (
    "供应链",
    "产业链",
    "关键材料",
    "技术依赖",
    "产能",
    "成本压力",
    "招股书",
    "上市传闻",
    "纳斯达克",
    "SpaceX",
)
ECOMMERCE_THEME_PHRASES = (
    "情感共鸣",
    "消费者心理",
    "用户需求",
    "信任",
    "内容转化",
    "品牌表达",
    "情绪价值",
    "转化",
)
UNSUPPORTED_SPACEX_FACTS = (
    "政府合同",
    "私人融资",
    "不锈钢壳",
    "发动机",
    "地面设施",
    "未来的金矿",
    "一定受益",
    "必然影响",
)


SPACEX_TRANSCRIPT = (
    "SpaceX 上市传闻和招股书未披露引发讨论，但重点不是消息真假。"
    "内容继续讲到供应链风险、产业链机会，以及关键材料和产能压力可能被放大。"
)
ECOMMERCE_TRANSCRIPT = (
    "这条电商带货内容讲的是情感共鸣。一个品牌走出困境之后，反而失去最初打动用户的表达。"
    "消费者心理不是只看价格，而是看产品故事能不能说出自己的处境。"
    "短视频文案要把用户需求、信任和情绪价值讲出来，才更容易带来点赞、共鸣和内容转化。"
)


def _spacex_analysis():
    return {
        "topic": "SpaceX 上市传闻",
        "hook": "表面是 SpaceX 上市和招股书消息，背后是供应链风险和产业链机会。",
        "template": "先讲上市传闻，再讲供应链风险，最后讲产业链机会。",
        "source_video_core": {
            "core_event": "SpaceX 上市传闻和招股书未披露",
            "core_conflict": "消息真假背后是供应链风险和产业链机会",
            "key_entities": ["SpaceX", "供应链", "产业链", "关键材料", "产能"],
            "causal_chain": "如果资本化预期升温，关键材料和产能压力可能被放大",
            "business_implication": "产业链风险和机会值得继续观察",
            "audience_takeaway": "别只看招股书，要看供应链风险和产业链机会",
        },
    }


def _ecommerce_analysis():
    return {
        "topic": "电商带货中的情感共鸣",
        "hook": "表面是带货文案，背后是消费者心理和用户情感表达。",
        "selling_points": ["情感共鸣", "消费者心理", "用户需求", "内容转化"],
        "structure": ["困境变化", "初心丢失", "用户需求", "信任建立", "内容转化"],
        "template": "先讲走出困境但失去初心，再讲消费者心理、用户需求、信任和内容转化。",
        "source_video_core": {
            "core_event": "电商带货内容通过品牌走出困境但失去初心引发共鸣",
            "core_conflict": "表面是卖产品，背后是用户情感表达和消费者心理",
            "key_entities": ["电商", "带货", "情感共鸣", "消费者心理", "用户需求", "信任", "内容转化", "品牌表达"],
            "causal_chain": "产品故事说中用户处境，信任和情绪价值才更容易被放大",
            "business_implication": "内容转化机会来自情感共鸣、用户信任和品牌表达",
            "audience_takeaway": "别只讲卖点，要讲用户需求、情感共鸣和信任",
        },
    }


def _cta_count(script: str) -> int:
    return sum(len(pattern.findall(script)) for pattern in CTA_PATTERNS)


def _assert_common_clean(script: str) -> None:
    for phrase in SYSTEM_OR_HARD_PHRASES:
        assert phrase not in script
    assert _cta_count(script) <= 1
    assert "互动你觉得" not in script
    assert "判断 我更想提醒" not in script


def test_spacex_theme_still_allows_source_supported_supply_chain_terms():
    rewrites = _fallback_rewrites(_spacex_analysis(), SPACEX_TRANSCRIPT)

    assert [item["title"] for item in rewrites] == REWRITE_TITLES
    assert len(rewrites) == 3
    joined = "\n".join(item["script"] for item in rewrites)
    assert "SpaceX" in joined
    assert any(term in joined for term in ("供应链", "产业链"))
    assert any(term in joined for term in ("风险", "机会"))
    for phrase in UNSUPPORTED_SPACEX_FACTS:
        assert phrase not in joined
    for item in rewrites:
        _assert_common_clean(item["script"])


def test_ecommerce_emotion_theme_does_not_inherit_supply_chain_language():
    rewrites = _normalize_rewrites(
        [
            {"title": "版本A：热点反差版", "script": "这条内容的反差是产业链变化，哪一段产业链可能被重新关注。"},
            {"title": "版本B：用户痛点版", "script": "先把产业链关系说清楚，再讲供应链风险和机会。"},
            {"title": "版本C：商业机会版", "script": "商业机会版要看关键材料、技术依赖、产能和成本压力。"},
        ],
        _ecommerce_analysis(),
        ECOMMERCE_TRANSCRIPT,
    )

    assert [item["title"] for item in rewrites] == REWRITE_TITLES
    assert len(rewrites) == 3
    joined = "\n".join(item["script"] for item in rewrites)
    for phrase in SUPPLY_CHAIN_PHRASES:
        assert phrase not in joined
    assert sum(1 for phrase in ECOMMERCE_THEME_PHRASES if phrase in joined) >= 4
    assert any(term in rewrites[2]["script"] for term in ("内容转化", "用户信任", "信任", "品牌表达", "情绪价值"))
    for item in rewrites:
        _assert_common_clean(item["script"])
