from app.services.viral_pipeline import REWRITE_TITLES, _fallback_rewrites, _normalize_rewrites


CTA_PHRASES = (
    "评论区说说你的判断",
    "把这个拆法先记下来，下一次热点就能直接套用",
    "后面如果这个方向继续有新变化，我会再单独拆给你看",
)
SYSTEM_PHRASES = (
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
PLACEHOLDER_PHRASES = (
    "短视频内容拆解",
    "不是 X 不行",
    "不是X不行",
    "适合自己的 Y",
    "适合自己的Y",
)
SPACEX_UNSUPPORTED = (
    "IPO",
    "SPAC",
    "资产注入",
    "政府合同",
    "私人融资",
    "不锈钢壳",
    "发动机",
    "地面设施",
    "未来金矿",
    "一定受益",
    "必然影响",
    "技术壁垒",
)


def _joined(rewrites: list[dict[str, str]]) -> str:
    return "\n".join(item["script"] for item in rewrites)


def _assert_common(rewrites: list[dict[str, str]]) -> None:
    assert [item["title"] for item in rewrites] == REWRITE_TITLES
    assert len(rewrites) == 3
    for item in rewrites:
        script = item["script"]
        for phrase in SYSTEM_PHRASES:
            assert phrase not in script
        assert sum(script.count(phrase) for phrase in CTA_PHRASES) <= 1
        assert "互动你觉得" not in script


def _spacex_analysis():
    return {
        "topic": "SpaceX 上市传闻",
        "hook": "表面是 SpaceX 上市和纳斯达克传闻，招股书还没有披露，但更多线索指向商业隐忧。",
        "selling_points": ["上市传闻", "招股书未披露", "线索指向供应链", "产业链风险机会"],
        "structure": ["SpaceX", "纳斯达克传闻", "招股书未披露", "供应链线索", "产业链风险", "机会判断"],
        "template": "先讲 SpaceX 上市传闻和招股书未披露，再讲线索指向供应链/产业链风险机会。",
        "source_video_core": {
            "core_event": "SpaceX 上市传闻和招股书未披露",
            "core_conflict": "市场预期和商业隐忧之间有反差",
            "key_entities": ["SpaceX", "纳斯达克", "招股书", "供应链", "产业链"],
            "causal_chain": "表层消息引发关注，后续线索指向供应链和产业链风险机会",
            "business_implication": "风险和机会需要放回产业链里看",
            "audience_takeaway": "别只看真假，要看背后的风险和机会",
        },
    }


def _ecommerce_analysis():
    return {
        "topic": "电商带货中的情感共鸣",
        "hook": "表面是带货文案，背后是消费者心理和用户情感表达。",
        "selling_points": ["情感共鸣", "消费者心理", "用户需求", "内容转化"],
        "structure": ["初心丢失", "用户需求", "信任建立", "内容转化"],
        "template": "先讲消费者心理，再讲用户需求、信任和内容转化。",
        "source_video_core": {
            "core_event": "电商带货内容通过情感共鸣打动用户",
            "core_conflict": "表面是卖产品，背后是用户情感表达和消费者心理",
            "key_entities": ["电商", "带货", "情感共鸣", "消费者心理", "用户需求", "信任", "内容转化", "品牌表达"],
            "causal_chain": "产品故事说中用户处境，信任和情绪价值才更容易被放大",
            "business_implication": "内容转化机会来自情感共鸣、用户信任和品牌表达",
            "audience_takeaway": "别只讲卖点，要讲用户需求、情感共鸣和信任",
        },
    }


def _growth_analysis():
    return {
        "topic": "李明博野心奋斗",
        "hook": "表面是逆袭故事，背后是困境、野心、执行和目标感。",
        "selling_points": ["李明博", "野心", "逆袭", "困境", "执行", "目标", "学习"],
        "structure": ["困境", "野心", "执行", "学习", "目标"],
        "template": "先讲困境，再讲野心和执行，最后讲目标和学习。",
        "source_video_core": {
            "core_event": "李明博在困境里靠野心和执行往前走",
            "core_conflict": "不是空喊逆袭，而是目标、学习和执行一点点累积",
            "key_entities": ["李明博", "野心", "逆袭", "困境", "执行", "目标", "学习"],
            "causal_chain": "困境带来压力，执行和学习让改变慢慢发生",
            "business_implication": "内容机会来自人群痛点、服务和内容产品化",
            "audience_takeaway": "别只看逆袭结果，要看每天怎么执行",
        },
    }


def _maijia_analysis():
    return {
        "topic": "麦家谈人生低谷",
        "hook": "表面是人生什么时候开始衰老，背后是巨大挫折和内心创伤有没有真的过去。",
        "selling_points": ["麦家", "巨大挫折", "痛苦", "外人以为你迈过坎", "只有你自己清楚", "低谷", "创伤", "内心修复"],
        "structure": ["人生变化", "巨大挫折", "痛苦", "低谷", "创伤", "自我重建"],
        "template": "先讲人生什么时候开始衰老，再讲外人以为你迈过坎，最后讲只有自己清楚创伤是否过去。",
        "source_video_core": {
            "core_event": "麦家谈人生什么时候开始衰老",
            "core_conflict": "外人以为你迈过了那道坎，但只有自己清楚痛苦和创伤有没有过去",
            "key_entities": ["麦家", "低谷", "巨大挫折", "痛苦", "创伤", "内心修复", "自我重建"],
            "causal_chain": "巨大挫折带来痛苦，外界只看到结果，自己才知道内心有没有修复",
            "business_implication": "表达机会更适合心理成长、陪伴型内容、书籍课程或咨询内容",
            "audience_takeaway": "别只看别人以为你走出来，要看内心是否真的修复",
        },
    }


def test_continuous_tasks_do_not_leak_previous_theme_domains():
    spacex = _fallback_rewrites(_spacex_analysis(), "SpaceX 上市传闻，招股书未披露，线索指向供应链和产业链风险机会。")
    ecommerce = _normalize_rewrites(
        [{"title": "版本A：热点反差版", "script": "产业链变化和SpaceX招股书值得关注。"}],
        _ecommerce_analysis(),
        "电商带货内容讲情感共鸣、消费者心理、用户需求、信任和内容转化。",
    )
    growth = _normalize_rewrites(
        [{"title": "版本A：热点反差版", "script": "电商带货转化和品牌表达是关键。"}],
        _growth_analysis(),
        "李明博野心奋斗，困境、执行、目标和学习让他完成自我改变。",
    )
    maijia = _normalize_rewrites(
        [{"title": "版本A：热点反差版", "script": "短视频内容拆解，不是 X 不行，而是你没有找到适合自己的 Y。"}],
        _maijia_analysis(),
        "麦家说人生什么时候开始衰老，巨大挫折和痛苦之后，外人以为你迈过坎，只有你自己清楚创伤有没有过去。",
    )

    for rewrites in (spacex, ecommerce, growth, maijia):
        _assert_common(rewrites)

    ecommerce_text = _joined(ecommerce)
    for phrase in ("SpaceX", "招股书", "供应链", "产业链"):
        assert phrase not in ecommerce_text

    growth_text = _joined(growth)
    for phrase in ("电商", "带货", "内容转化", "品牌表达", "供应链", "产业链", "SpaceX"):
        assert phrase not in growth_text

    maijia_text = _joined(maijia)
    for phrase in (*PLACEHOLDER_PHRASES, "电商转化", "内容转化", "产业链", "供应链", "SpaceX"):
        assert phrase not in maijia_text

    spacex_text = _joined(spacex)
    for phrase in ("情感共鸣", "自我改变", "内心修复", "创伤"):
        assert phrase not in spacex_text


def test_spacex_keeps_supply_chain_without_unsupported_financial_paths():
    rewrites = _normalize_rewrites(
        [
            {"title": "版本A：热点反差版", "script": "SpaceX可能通过IPO、SPAC或资产注入走向资本市场。"},
            {"title": "版本B：用户痛点版", "script": "只看官方文件最靠谱，别管供应链。"},
            {"title": "版本C：商业机会版", "script": "未来金矿一定受益。"},
        ],
        _spacex_analysis(),
        "SpaceX 上市传闻和纳斯达克讨论升温，招股书未披露，线索指向供应链和产业链风险机会。",
    )
    _assert_common(rewrites)
    text = _joined(rewrites)
    assert any(term in text for term in ("供应链", "产业链"))
    assert "风险" in text and "机会" in text
    for phrase in SPACEX_UNSUPPORTED:
        assert phrase not in text


def test_maijia_emotional_recovery_keeps_real_theme_and_avoids_templates():
    rewrites = _normalize_rewrites(
        [
            {"title": "版本A：热点反差版", "script": "短视频内容拆解，不是 X 不行，而是你没有找到适合自己的 Y。"},
            {"title": "版本B：用户痛点版", "script": "电商带货转化要抓用户需求和品牌表达。"},
            {"title": "版本C：商业机会版", "script": "产业链机会和供应链变化值得关注。"},
        ],
        _maijia_analysis(),
        "麦家谈人生什么时候开始衰老，巨大挫折、痛苦、低谷和创伤之后，外人以为你迈过坎，只有你自己清楚内心有没有修复。",
    )
    _assert_common(rewrites)
    text = _joined(rewrites)
    assert sum(1 for phrase in ("麦家", "低谷", "痛苦", "挫折", "创伤", "内心", "自我重建") if phrase in text) >= 4
    for phrase in (*PLACEHOLDER_PHRASES, "供应链", "产业链", "电商带货", "内容转化", "品牌表达", "SpaceX", "招股书", "上市", "纳斯达克"):
        assert phrase not in text


def test_weak_evidence_degrades_to_neutral_spoken_scripts():
    rewrites = _normalize_rewrites(
        [
            {"title": "版本A：热点反差版", "script": "不是 X 不行，而是你没有找到适合自己的 Y。"},
            {"title": "版本B：用户痛点版", "script": "短视频内容拆解可以套供应链和电商转化。"},
        ],
        {
            "topic": "短视频内容拆解",
            "hook": "如何抓住用户注意力",
            "template": "不是 X 不行，而是你没有找到适合自己的 Y。",
            "source_video_core": {},
        },
        "如何抓住用户注意力。",
    )
    _assert_common(rewrites)
    text = _joined(rewrites)
    for phrase in (*PLACEHOLDER_PHRASES, "供应链", "产业链", "电商转化", "成长逆袭", "麦家", "创伤"):
        assert phrase not in text
    assert "而是你没有找到" not in text
    assert "这个话题" in text or "用户注意力" in text
