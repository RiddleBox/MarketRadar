"""
分析簇首 vs 簇尾的准确率差异

验证假设：簇尾（趋势已显现）比簇首（需要预测）更容易判断
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from m11_agent_sim.agent_network import AgentNetwork
from m11_agent_sim.event_catalog import load_event_catalog, set_sentiment_provider
from m11_agent_sim.sentiment_provider import DecorrelatedSentimentProvider
from datetime import datetime

# 设置去相关情绪数据源
set_sentiment_provider(DecorrelatedSentimentProvider())

# 加载事件
events = load_event_catalog(min_events=50)
sorted_events = sorted(events, key=lambda x: datetime.strptime(x.date, "%Y-%m-%d"))

# 标记簇首和簇尾
def mark_cluster_position(events, max_gap_days=3):
    """标记每个事件是簇首、簇尾还是孤立事件"""
    marked = []

    for i, event in enumerate(events):
        curr_date = datetime.strptime(event.date, "%Y-%m-%d")

        # 检查前一个事件
        is_continuation = False
        if i > 0:
            prev_event = events[i-1]
            prev_date = datetime.strptime(prev_event.date, "%Y-%m-%d")
            gap = (curr_date - prev_date).days
            if gap <= max_gap_days and prev_event.actual_direction == event.actual_direction:
                is_continuation = True

        # 检查后一个事件
        has_next = False
        if i < len(events) - 1:
            next_event = events[i+1]
            next_date = datetime.strptime(next_event.date, "%Y-%m-%d")
            gap = (next_date - curr_date).days
            if gap <= max_gap_days and next_event.actual_direction == event.actual_direction:
                has_next = True

        # 分类
        if is_continuation and has_next:
            position = "middle"
        elif is_continuation:
            position = "tail"
        elif has_next:
            position = "head"
        else:
            position = "isolated"

        marked.append((event, position))

    return marked

marked_events = mark_cluster_position(sorted_events)

# 测试不同位置的准确率
network = AgentNetwork._default_a_share(use_llm=False, min_confidence=0.50)

results_by_position = {
    "head": {"correct": 0, "total": 0, "skipped": 0},
    "middle": {"correct": 0, "total": 0, "skipped": 0},
    "tail": {"correct": 0, "total": 0, "skipped": 0},
    "isolated": {"correct": 0, "total": 0, "skipped": 0},
}

print("=" * 100)
print("簇位置分析")
print("=" * 100)

for event, position in marked_events:
    dist = network.run(event.market_input)

    if dist.no_trade:
        results_by_position[position]["skipped"] += 1
        continue

    results_by_position[position]["total"] += 1
    if dist.direction == event.actual_direction:
        results_by_position[position]["correct"] += 1

print(f"\n{'位置':<10} {'总数':<8} {'跳过':<8} {'判断':<8} {'正确':<8} {'准确率':<10}")
print("=" * 100)

for position in ["head", "middle", "tail", "isolated"]:
    stats = results_by_position[position]
    total_events = stats["total"] + stats["skipped"]
    accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0

    pos_name = {
        "head": "簇首",
        "middle": "簇中",
        "tail": "簇尾",
        "isolated": "孤立"
    }[position]

    print(f"{pos_name:<10} {total_events:<8} {stats['skipped']:<8} {stats['total']:<8} {stats['correct']:<8} {accuracy:<10.1%}")

# 对比簇首+孤立 vs 簇中+簇尾
predictive_correct = results_by_position["head"]["correct"] + results_by_position["isolated"]["correct"]
predictive_total = results_by_position["head"]["total"] + results_by_position["isolated"]["total"]
predictive_acc = predictive_correct / predictive_total if predictive_total > 0 else 0

reactive_correct = results_by_position["middle"]["correct"] + results_by_position["tail"]["correct"]
reactive_total = results_by_position["middle"]["total"] + results_by_position["tail"]["total"]
reactive_acc = reactive_correct / reactive_total if reactive_total > 0 else 0

print("\n" + "=" * 100)
print("预测能力 vs 反应能力")
print("=" * 100)
print(f"预测能力（簇首+孤立）: {predictive_acc:.1%} ({predictive_correct}/{predictive_total})")
print(f"反应能力（簇中+簇尾）: {reactive_acc:.1%} ({reactive_correct}/{reactive_total})")
print(f"\n差距: {reactive_acc - predictive_acc:+.1%}")
print(f"\n结论: {'簇尾更容易判断（事后诸葛亮）' if reactive_acc > predictive_acc else '预测能力强于反应'}")
