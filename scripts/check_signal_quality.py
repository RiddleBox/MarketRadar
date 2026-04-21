"""
检查ANNOTATED_EVENTS信号质量

验证：16个手动标注事件的signal_dir vs 实际5日收益方向的一致性
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from m11_agent_sim.event_catalog import ANNOTATED_EVENTS, load_event_catalog, set_sentiment_provider
from m11_agent_sim.sentiment_provider import DecorrelatedSentimentProvider

# 设置去相关情绪数据源
set_sentiment_provider(DecorrelatedSentimentProvider())

# 加载事件
events = load_event_catalog(min_events=50)

print("=" * 100)
print("ANNOTATED_EVENTS 信号质量检查")
print("=" * 100)

print(f"\n手动标注事件数: {len(ANNOTATED_EVENTS)}")
print(f"总事件数: {len(events)}")

# 找出标注事件对应的实际事件
annotated_dates = {ann["date"]: ann for ann in ANNOTATED_EVENTS}
matched_events = []

for event in events:
    if event.date in annotated_dates:
        ann = annotated_dates[event.date]
        matched_events.append((ann, event))

print(f"匹配到的事件: {len(matched_events)}")

print("\n" + "=" * 100)
print("信号方向 vs 实际方向对比")
print("=" * 100)
print(f"{'日期':<12} {'信号':<10} {'实际':<10} {'实际收益':<10} {'一致?':<8} {'描述':<50}")
print("=" * 100)

matches = 0
total = 0

for ann, event in matched_events:
    signal_dir = ann["signal_dir"]
    actual_dir = event.actual_direction
    actual_ret = event.actual_5d_return
    is_match = (signal_dir == actual_dir)

    if is_match:
        matches += 1
    total += 1

    match_mark = "OK" if is_match else "MISS"

    print(f"{event.date:<12} {signal_dir:<10} {actual_dir:<10} {actual_ret:>+9.1%} {match_mark:<8} {ann['desc'][:50]}")

accuracy = matches / total if total > 0 else 0

print("\n" + "=" * 100)
print("信号质量评估")
print("=" * 100)
print(f"信号准确率: {accuracy:.1%} ({matches}/{total})")

# 按方向分析
from collections import defaultdict
by_signal = defaultdict(lambda: {"correct": 0, "total": 0})

for ann, event in matched_events:
    signal_dir = ann["signal_dir"]
    is_match = (signal_dir == event.actual_direction)
    by_signal[signal_dir]["total"] += 1
    if is_match:
        by_signal[signal_dir]["correct"] += 1

print(f"\n按信号方向分析:")
for signal_dir in ["BULLISH", "NEUTRAL", "BEARISH"]:
    stats = by_signal[signal_dir]
    if stats["total"] > 0:
        acc = stats["correct"] / stats["total"]
        print(f"  {signal_dir:8s}: {acc:.1%} ({stats['correct']}/{stats['total']})")

print(f"\n" + "=" * 100)
print("结论")
print("=" * 100)
if accuracy >= 0.70:
    print(f"✓ 信号质量良好（≥70%），可以作为Agent校准的ground truth")
    print(f"  Agent的任务是'模拟市场对信号的反应'，目标是达到信号准确率")
elif accuracy >= 0.50:
    print(f"⚠ 信号质量中等（50-70%），Agent最多只能达到这个准确率")
    print(f"  需要改进信号标注质量，或者重新定义Agent的任务")
else:
    print(f"✗ 信号质量差（<50%），必须重新标注信号")
    print(f"  当前信号与实际收益方向不一致，Agent无法学习")

print(f"\n关键洞察:")
print(f"  - 如果信号准确率是X%，Agent理论上限也是X%")
print(f"  - Agent的61.7%准确率可能来自'忽略错误信号'（置信度门控）")
print(f"  - 真正的优化方向是提升信号质量，而不是调整Agent参数")
