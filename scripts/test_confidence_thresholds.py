"""
测试规则模式在不同置信度阈值下的表现

目标：找到最优阈值，使方向命中率达到或接近 70%
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
print(f"加载 {len(events)} 个历史事件\n")

# 测试不同置信度阈值
thresholds = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]

print("=" * 80)
print(f"{'阈值':<8} {'命中率':<10} {'选择性准确率':<15} {'跳过率':<10} {'综合得分':<10}")
print("=" * 80)

results = []
for threshold in thresholds:
    network = AgentNetwork._default_a_share(use_llm=False, min_confidence=threshold)
    calibrator = HistoricalCalibrator(network=network)
    score = calibrator.calibrate(events, persist=False)

    results.append({
        'threshold': threshold,
        'accuracy': score.direction_accuracy,
        'selective_acc': score.selective_accuracy,
        'selective_n': score.selective_n,
        'total': score.total_events,
        'skip_rate': score.skip_rate,
        'composite': score.composite_score
    })

    print(f"{threshold:<8.2f} {score.direction_accuracy:<10.1%} "
          f"{score.selective_accuracy:<7.1%}({score.selective_n:>2}/{score.total_events:<2}) "
          f"{score.skip_rate:<10.1%} {score.composite_score:<10.1f}")

# 找到最优阈值
print("\n" + "=" * 80)
print("分析结果")
print("=" * 80)

best_accuracy = max(results, key=lambda x: x['accuracy'])
best_composite = max(results, key=lambda x: x['composite'])

print(f"\n最高命中率: {best_accuracy['threshold']:.2f} → {best_accuracy['accuracy']:.1%}")
print(f"最高综合得分: {best_composite['threshold']:.2f} → {best_composite['composite']:.1f}")

# 找到达到 70% 的阈值（如果有）
达标阈值 = [r for r in results if r['accuracy'] >= 0.70]
if 达标阈值:
    print(f"\n✅ 达到 70% 准入标准的阈值:")
    for r in 达标阈值:
        print(f"  - {r['threshold']:.2f}: {r['accuracy']:.1%} (跳过率 {r['skip_rate']:.1%})")
else:
    print(f"\n⚠️  未达到 70% 准入标准")
    print(f"   最高命中率: {best_accuracy['accuracy']:.1%} (差距 {0.70 - best_accuracy['accuracy']:.1%})")

    # 预测需要的阈值
    if len(results) >= 3:
        # 简单线性外推
        high_thresh = results[-1]
        mid_thresh = results[-2]
        if high_thresh['accuracy'] > mid_thresh['accuracy']:
            slope = (high_thresh['accuracy'] - mid_thresh['accuracy']) / (high_thresh['threshold'] - mid_thresh['threshold'])
            needed_thresh = high_thresh['threshold'] + (0.70 - high_thresh['accuracy']) / slope
            if 0 < needed_thresh <= 1.0:
                print(f"   预测需要阈值: ~{needed_thresh:.2f} (线性外推)")
