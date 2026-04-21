"""
分析 M11 规则模式的 miss patterns

目标：找出哪些类型的事件容易判断错误，为优化提供方向
"""
import sys
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from m11_agent_sim.agent_network import AgentNetwork
from m11_agent_sim.calibrator import HistoricalCalibrator
from m11_agent_sim.event_catalog import load_event_catalog, set_sentiment_provider
from m11_agent_sim.sentiment_provider import DecorrelatedSentimentProvider

# 设置去相关情绪数据源
set_sentiment_provider(DecorrelatedSentimentProvider())

# 加载事件
events = load_event_catalog(min_events=50)
print(f"加载 {len(events)} 个历史事件\n")

# 运行校准（最优阈值 0.50）
network = AgentNetwork._default_a_share(use_llm=False, min_confidence=0.50)
calibrator = HistoricalCalibrator(network=network)
score = calibrator.calibrate(events, persist=False)

# 从校准结果获取详细案例
cases = score.details  # CalibrationScore.details 包含所有 ValidationCase

print("=" * 80)
print("整体统计")
print("=" * 80)
print(f"总事件数: {score.total_events}")
print(f"方向命中: {int(score.direction_accuracy * score.total_events)}")
print(f"方向错误: {score.total_events - int(score.direction_accuracy * score.total_events)}")
print(f"跳过事件: {int(score.skip_rate * score.total_events)}")

# 分析 miss patterns
print("\n" + "=" * 80)
print("Miss Patterns 分析")
print("=" * 80)

miss_patterns = Counter()
miss_cases = []

for case in cases:
    if not case.get('direction_match', True):
        actual = case.get('actual_direction', 'UNKNOWN')
        simulated = case.get('simulated_direction', 'UNKNOWN')
        miss_patterns[(actual, simulated)] += 1
        miss_cases.append(case)

print(f"\n错误分类统计 (共 {len(miss_cases)} 个):")
for (actual, sim), count in miss_patterns.most_common():
    print(f"  {actual:8} -> {sim:8}: {count:2} 次 ({count/len(miss_cases)*100:.1f}%)")

# 按实际方向分组分析
print("\n" + "=" * 80)
print("按实际方向分组分析")
print("=" * 80)

by_actual = defaultdict(lambda: {'total': 0, 'correct': 0, 'wrong': 0, 'cases': []})

for case in cases:
    actual = case.get('actual_direction', 'UNKNOWN')
    match = case.get('direction_match', False)

    by_actual[actual]['total'] += 1
    if match:
        by_actual[actual]['correct'] += 1
    else:
        by_actual[actual]['wrong'] += 1
        by_actual[actual]['cases'].append(case)

for direction in ['BULLISH', 'NEUTRAL', 'BEARISH']:
    if direction in by_actual:
        stats = by_actual[direction]
        accuracy = stats['correct'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"\n{direction}:")
        print(f"  总数: {stats['total']}, 正确: {stats['correct']}, 错误: {stats['wrong']}")
        print(f"  准确率: {accuracy:.1f}%")

        if stats['cases']:
            print(f"  错误案例:")
            for c in stats['cases'][:5]:  # 只显示前5个
                date = c.get('date', '?')
                desc = c.get('description', '?')[:40]
                sim = c.get('simulated_direction', '?')
                ret5 = c.get('actual_5d_return', 0) * 100
                print(f"    {date} 预测:{sim:8} 实际涨跌:{ret5:+.1f}% | {desc}")

# 分析价格幅度与错误率的关系
print("\n" + "=" * 80)
print("价格幅度与错误率分析")
print("=" * 80)

price_buckets = {
    '大涨(>8%)': [],
    '中涨(5-8%)': [],
    '小涨(3-5%)': [],
    '震荡(-3~3%)': [],
    '小跌(-5~-3%)': [],
    '中跌(-8~-5%)': [],
    '大跌(<-8%)': []
}

for case in cases:
    ret5 = case.get('actual_5d_return', 0)
    match = case.get('direction_match', False)

    if ret5 > 0.08:
        price_buckets['大涨(>8%)'].append(match)
    elif ret5 > 0.05:
        price_buckets['中涨(5-8%)'].append(match)
    elif ret5 > 0.03:
        price_buckets['小涨(3-5%)'].append(match)
    elif ret5 > -0.03:
        price_buckets['震荡(-3~3%)'].append(match)
    elif ret5 > -0.05:
        price_buckets['小跌(-3~-5%)'].append(match)
    elif ret5 > -0.08:
        price_buckets['中跌(-5~-8%)'].append(match)
    else:
        price_buckets['大跌(<-8%)'].append(match)

for bucket, matches in price_buckets.items():
    if matches:
        accuracy = sum(matches) / len(matches) * 100
        print(f"{bucket:15}: {len(matches):2} 个事件, 准确率 {accuracy:5.1f}%")

# 关键洞察
print("\n" + "=" * 80)
print("关键洞察与优化建议")
print("=" * 80)

# 找出最大的问题
max_miss = miss_patterns.most_common(1)[0] if miss_patterns else None
if max_miss:
    (actual, sim), count = max_miss
    print(f"\n1. 最大问题: {actual} -> {sim} ({count} 次)")
    print(f"   占所有错误的 {count/len(miss_cases)*100:.1f}%")

# NEUTRAL 识别问题
neutral_stats = by_actual.get('NEUTRAL', {})
if neutral_stats.get('total', 0) > 0:
    neutral_acc = neutral_stats['correct'] / neutral_stats['total'] * 100
    print(f"\n2. NEUTRAL 识别准确率: {neutral_acc:.1f}%")
    if neutral_acc < 50:
        print(f"   ⚠️ NEUTRAL 识别是主要瓶颈")
        print(f"   建议: 提高 NEUTRAL 判断的阈值或增强震荡市识别逻辑")

# 极端行情识别
extreme_cases = [c for c in cases if abs(c.get('actual_5d_return', 0)) > 0.08]
if extreme_cases:
    extreme_correct = sum(1 for c in extreme_cases if c.get('direction_match', False))
    extreme_acc = extreme_correct / len(extreme_cases) * 100
    print(f"\n3. 极端行情(>8%)识别准确率: {extreme_acc:.1f}%")
    if extreme_acc > 70:
        print(f"   ✓ 极端行情识别较好")
    else:
        print(f"   ⚠️ 极端行情识别需要改进")
