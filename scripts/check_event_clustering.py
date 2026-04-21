"""
检查连续BEARISH事件是否是同一趋势

目标：验证2024-11-12到11-15这4个误判是否是同一下跌趋势
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from m11_agent_sim.event_catalog import load_event_catalog, set_sentiment_provider
from m11_agent_sim.sentiment_provider import DecorrelatedSentimentProvider
from datetime import datetime, timedelta

# 设置去相关情绪数据源
set_sentiment_provider(DecorrelatedSentimentProvider())

# 加载事件
events = load_event_catalog(min_events=50)

# 找出所有BEARISH事件
bearish_events = sorted(
    [e for e in events if e.actual_direction == "BEARISH"],
    key=lambda x: datetime.strptime(x.date, "%Y-%m-%d")
)

print("=" * 100)
print("BEARISH 事件时间分布")
print("=" * 100)

for i, event in enumerate(bearish_events):
    date = datetime.strptime(event.date, "%Y-%m-%d")

    # 检查是否有相邻事件
    prev_gap = None
    next_gap = None

    if i > 0:
        prev_date = datetime.strptime(bearish_events[i-1].date, "%Y-%m-%d")
        prev_gap = (date - prev_date).days

    if i < len(bearish_events) - 1:
        next_date = datetime.strptime(bearish_events[i+1].date, "%Y-%m-%d")
        next_gap = (next_date - date).days

    gap_info = ""
    if prev_gap and prev_gap <= 3:
        gap_info += f" [距上个事件{prev_gap}天]"
    if next_gap and next_gap <= 3:
        gap_info += f" [距下个事件{next_gap}天]"

    print(f"{event.date}  {event.actual_5d_return:+6.1%}  {event.description[:40]:40s}{gap_info}")

print("\n" + "=" * 100)
print("连续事件分析")
print("=" * 100)

# 找出连续事件（间隔<=3天）
clusters = []
current_cluster = [bearish_events[0]]

for i in range(1, len(bearish_events)):
    prev_date = datetime.strptime(bearish_events[i-1].date, "%Y-%m-%d")
    curr_date = datetime.strptime(bearish_events[i].date, "%Y-%m-%d")
    gap = (curr_date - prev_date).days

    if gap <= 3:
        current_cluster.append(bearish_events[i])
    else:
        if len(current_cluster) > 1:
            clusters.append(current_cluster)
        current_cluster = [bearish_events[i]]

if len(current_cluster) > 1:
    clusters.append(current_cluster)

if clusters:
    print(f"\n发现 {len(clusters)} 个连续事件簇:\n")
    for i, cluster in enumerate(clusters, 1):
        print(f"簇 {i}: {len(cluster)} 个事件")
        for event in cluster:
            print(f"  {event.date}  {event.actual_5d_return:+6.1%}  {event.description[:50]}")
        print()
else:
    print("\n未发现连续事件（间隔<=3天）")

print("=" * 100)
print("结论")
print("=" * 100)
print(f"总BEARISH事件: {len(bearish_events)}")
print(f"连续事件簇: {len(clusters)}")
if clusters:
    total_clustered = sum(len(c) for c in clusters)
    print(f"簇内事件数: {total_clustered} ({total_clustered/len(bearish_events):.1%})")
    print(f"\n建议: 连续事件可能是同一趋势的不同观测点，应该:")
    print(f"  1. 只保留每个簇的第一个事件作为独立样本")
    print(f"  2. 或者调整事件定义，避免重复采样同一趋势")
