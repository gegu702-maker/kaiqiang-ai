from __future__ import annotations

import argparse
import asyncio
import json
import time

from app.services import viral_analyzer
from app.services.viral_diagnostics import bind_request_id, new_request_id, reset_request_id


FINANCE_FIXTURE = """
最近的资本市场出现了一组值得放在一起观察的信号。表面上看，是多个交易日的指数波动和板块轮动，真正需要拆开的，是不同参与者为什么在同一阶段连续表达长期信心。五大保险机构先后发声，讨论稳定市场预期、服务实体经济和支持新兴产业。看这类信息时，不能把机构表态直接理解成短期涨跌承诺，还要继续观察后续资金安排、资产配置方向和执行节奏。
第二个信号来自上市公司的增持与回购。回购并不只有一种目的，有的用于员工激励，有的用于市值管理，也有公司明确推进注销式回购。注销后总股本减少，在其他条件不变时，每股收益可能得到增厚，股东权益结构也会发生变化。但判断回购质量，不能只看公告标题，还要看资金来源、实际完成比例、回购价格区间以及公司基本面。如果经营没有改善，单独一项回购并不能替代对现金流、盈利能力和行业周期的判断。
第三个信号是专业投资机构的自购和ETF申购。知名私募、公募以及其他长期资金用真金白银表达态度，确实比单纯发言多了一层行动信息。普通用户更适合先确认资金用途和时间边界，再判断相关指数产品是否与自己的风险偏好一致，而不是因为看到机构动作就追随短期情绪。
第四个观察点是中报预告和产业链业绩。部分公司披露的经营变化，让市场重新讨论半导体等产业链的景气线索。分析这类信息，需要区分订单改善、价格变化、库存周期和一次性收益，不能把单家公司表现直接外推到整个行业。沪深三百、中证五百、科创五十等指数覆盖的公司结构不同，ETF表现也会受到成分权重和市场风格影响，所以同一天的上涨并不意味着背后的驱动完全一致。
最后还要看外资机构的长期视角。花旗集团、摩根士丹利等机构的观点可以作为市场观察样本，但它们使用的假设、估值框架和客户期限未必相同。把保险资金、上市公司回购、机构自购、ETF申购、中报线索和外资观点放在一起，能够看到信心正在从表达走向部分行动；可这仍然不是确定性买入信号。更稳妥的做法，是继续核对公告进度、经营数据与资金流向，保留风险边界，用持续证据修正判断。
""".strip()


EMOTIONAL_FIXTURE = """
有些关系，不是突然结束的。只是从某一天开始，你发出的消息，要等很久。你认真说的话，被一句没事带过。你以为对方只是忙，于是一次次替他解释，也一次次把自己的失落收回去。
后来你才明白，真正让人难过的，不是一次争吵。是你站在原地，等一个越来越敷衍的回应。你不敢追问，怕显得敏感。你假装轻松，怕给别人压力。可那些没有说出口的话，并没有消失。它们只是慢慢堆在心里。
如果你也经历过这样的时刻，先别急着责怪自己。重视一段关系，不代表你做错了什么。你可以停下来，听听自己的感受。哪些委屈可以沟通，哪些边界不能再退，哪些期待其实早已没有回应。
离开不一定意味着失败。留下也不一定代表深情。重要的是，你有没有在这段关系里被认真看见，有没有仍然保留真实的自己。给自己一点时间。慢一点，也没关系。答案不需要今天就出现。先把心安顿好，再决定下一步往哪里走。
""".strip()


class _Table:
    def insert(self, _payload):
        return self

    def execute(self):
        return None


class _Supabase:
    def table(self, _name):
        return _Table()


def _cjk_len(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


async def _run(fixture_name: str) -> dict:
    if fixture_name == "finance":
        source = FINANCE_FIXTURE
        effective_seconds = 167.6
    else:
        source = EMOTIONAL_FIXTURE
        effective_seconds = 120.0

    viral_analyzer._assert_viral_quota = lambda *_args, **_kwargs: {
        "plan": "pro",
        "used": 0,
        "monthly_limit": 99,
    }
    request_id = new_request_id()
    context = bind_request_id(request_id)
    started = time.perf_counter()
    try:
        result = await viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="p2-37-text-acceptance",
            email="p2-37-text-acceptance@example.invalid",
            raw_script=source,
            industry="knowledge" if fixture_name == "finance" else "personal_brand",
            language="zh",
            rewrite_length="match_source",
            effective_speech_seconds=effective_seconds,
        )
    finally:
        reset_request_id(context)

    return {
        "fixture": fixture_name,
        "request_id": request_id,
        "source_cjk": _cjk_len(source),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "diagnostic": result["diagnostic"],
        "scripts": [item["script"] for item in result["rewrites"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", choices=("finance", "emotional"))
    args = parser.parse_args()
    print(json.dumps(asyncio.run(_run(args.fixture)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
