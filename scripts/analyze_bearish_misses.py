"""
深度分析 BEARISH 误判案例

目标：找出为什么 70% 的 BEARISH 事件被误判为 NEUTRAL
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from m11_agent_sim.agent_network import AgentNetwork
from m11_agent_sim.calibrator import HistoricalCalibrator
from m11_agent_sim.event_catalog import load_event_catalog, set_sentiment_provider
from m11_agent_sim.sentiment_provider import DecorrelatedSentimentProvider

# 设置去相关情绪数据源
set_sentiment_provider(DecorrelatedSentimentProvider())

# 加载事件
events = load_event_catalog(min_events=50)

# 创建网络
network = AgentNetwork._default_a_share(use_llm=False, min_confidence=0.50)

print("=" * 100)
print("BEARISH 误判案例深度分析")
print("=" * 100)

bearish_events = [e for e in events if e.actual_direction == "BEARISH"]
print(f"\n总共 {len(bearish_events)} 个 BEARISH 事件\n")

misses = []
hits = []

for event in bearish_events:
    dist = network.run(event.market_input)
    if dist.direction == event.actual_direction:
        hits.append((event, dist))
    else:
        misses.append((event, dist))

print(f"命中: {len(hits)}/{len(bearish_events)} ({len(hits)/len(bearish_events):.1%})")
print(f"误判: {len(misses)}/{len(bearish_events)} ({len(misses)/len(bearish_events):.1%})")

print("\n" + "=" * 100)
print("误判案例详细分析")
print("=" * 100)

for i, (event, dist) in enumerate(misses, 1):
    p = event.market_input.price
    s = event.market_input.sentiment

    print(f"\n【案例 {i}】{event.date} - {event.description}")
    print(f"  实际: BEARISH ({event.actual_5d_return:+.1%})")
    print(f"  预测: {dist.direction} (多{dist.bullish_prob:.1%} 空{dist.bearish_prob:.1%} 中{dist.neutral_prob:.1%})")
    print(f"  置信度: {dist.confidence:.1%}")
    print(f"\n  价格特征:")
    print(f"    5日涨跌: {p.price_5d_chg_pct:+.1%}")
    print(f"    20日涨跌: {p.price_20d_chg_pct:+.1%}")
    print(f"    MA5: {p.ma5:.2f}, MA20: {p.ma20:.2f}, 当前: {p.current_price:.2f}")
    print(f"    站上MA5: {p.above_ma5}, 站上MA20: {p.above_ma20}")
    print(f"    量比: {p.volume_ratio:.2f}")
    print(f"\n  情绪特征:")
    print(f"    恐贪指数: {s.fear_greed_index:.1f}")
    print(f"    涨跌比: {s.advance_decline_ratio:.1%}")

    print(f"\n  各Agent判断:")
    # 重新运行获取详细输出
    from m11_agent_sim.agent_network import AgentNetwork
    net = AgentNetwork._default_a_share(use_llm=False, min_confidence=0.0)  # 不过滤
    outputs = net._run_sequential(event.market_input)
    for out in outputs:
        agent_name = {
            "policy": "政策",
            "northbound": "北向",
            "technical": "技术",
            "sentiment_retail": "散户",
            "fundamental": "基本面"
        }.get(out.agent_type, out.agent_type)
        print(f"    {agent_name:6s}: {out.direction:8s} (多{out.bullish_prob:.0%} 空{out.bearish_prob:.0%}) 置信{out.confidence:.0%}")

print("\n" + "=" * 100)
print("命中案例对比")
print("=" * 100)

for i, (event, dist) in enumerate(hits, 1):
    p = event.market_input.price
    s = event.market_input.sentiment

    print(f"\n【命中 {i}】{event.date} - {event.description}")
    print(f"  实际: BEARISH ({event.actual_5d_return:+.1%})")
    print(f"  预测: {dist.direction} (多{dist.bullish_prob:.1%} 空{dist.bearish_prob:.1%})")
    print(f"  价格: 5日{p.price_5d_chg_pct:+.1%} 20日{p.price_20d_chg_pct:+.1%} 量比{p.volume_ratio:.2f}")
    print(f"  情绪: FG={s.fear_greed_index:.1f}")
