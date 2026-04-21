"""
去重后的校准测试

策略：连续事件（间隔<=3天且同方向）只保留第一个
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from m11_agent_sim.agent_network import AgentNetwork
from m11_agent_sim.calibrator import HistoricalCalibrator
from m11_agent_sim.event_catalog import load_event_catalog, set_sentiment_provider
from m11_agent_sim.sentiment_provider import DecorrelatedSentimentProvider
from datetime import datetime

# 设置去相关情绪数据源
set_sentiment_provider(DecorrelatedSentimentProvider())

# 加载事件
events = load_event_catalog(min_events=50)

# 去重：连续事件只保留第一个
def deduplicate_events(events, max_gap_days=3):
    """去除连续同方向事件，只保留每个簇的第一个"""
    sorted_events = sorted(events, key=lambda x: datetime.strptime(x.date, "%Y-%m-%d"))

    deduped = []
    skip_until = None

    for i, event in enumerate(sorted_events):
        curr_date = datetime.strptime(event.date, "%Y-%m-%d")

        # 如果在跳过期内，跳过
        if skip_until and curr_date <= skip_until:
            continue

        # 保留当前事件
        deduped.append(event)

        # 检查后续事件是否连续
        for j in range(i+1, len(sorted_events)):
            next_event = sorted_events[j]
            next_date = datetime.strptime(next_event.date, "%Y-%m-%d")
            gap = (next_date - curr_date).days

            if gap > max_gap_days:
                break

            # 如果方向相同且间隔<=3天，标记为跳过
            if next_event.actual_direction == event.actual_direction:
                skip_until = next_date

    return deduped

events_deduped = deduplicate_events(events)

print("=" * 80)
print("事件去重分析")
print("=" * 80)
print(f"原始事件数: {len(events)}")
print(f"去重后事件数: {len(events_deduped)}")
print(f"去除事件数: {len(events) - len(events_deduped)}")

# 按方向统计
from collections import Counter
original_dist = Counter(e.actual_direction for e in events)
deduped_dist = Counter(e.actual_direction for e in events_deduped)

print(f"\n方向分布变化:")
for direction in ["BULLISH", "NEUTRAL", "BEARISH"]:
    orig = original_dist[direction]
    dedup = deduped_dist[direction]
    print(f"  {direction:8s}: {orig} → {dedup} ({dedup-orig:+d})")

# 测试去重后的准确率
print("\n" + "=" * 80)
print("去重后校准测试（min_confidence=0.50）")
print("=" * 80)

network = AgentNetwork._default_a_share(use_llm=False, min_confidence=0.50)
calibrator = HistoricalCalibrator(network=network)

# 手动运行校准（使用去重事件）
correct = 0
total = 0
skipped = 0

for event in events_deduped:
    dist = network.run(event.market_input)
    if dist.no_trade:
        skipped += 1
        continue

    total += 1
    if dist.direction == event.actual_direction:
        correct += 1

accuracy = correct / total if total > 0 else 0
skip_rate = skipped / len(events_deduped)

print(f"\n总事件数: {len(events_deduped)}")
print(f"跳过事件: {skipped} ({skip_rate:.1%})")
print(f"实际判断: {total}")
print(f"判断正确: {correct}")
print(f"方向命中率: {accuracy:.1%}")
print(f"\n对比原始数据（未去重）: 61.7%")
print(f"提升: {accuracy - 0.617:+.1%}")
