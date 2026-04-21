"""
测试优化后的Agent配置效果

对比：
1. 基线（原始配置）
2. 优化后（FundamentalAgent看空增强 + TechnicalAgent阈值降低 + 权重调整）
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

print("=" * 80)
print("测试配置：min_confidence=0.50（最优阈值）")
print("=" * 80)

# 测试基线配置
print("\n【基线配置】")
network_baseline = AgentNetwork._default_a_share(use_llm=False, min_confidence=0.50)
calibrator_baseline = HistoricalCalibrator(network=network_baseline)
score_baseline = calibrator_baseline.calibrate(events, persist=False)

print(f"方向命中率: {score_baseline.direction_accuracy:.1%}")
print(f"选择性准确率: {score_baseline.selective_accuracy:.1%} ({score_baseline.selective_n}/{score_baseline.total_events})")
print(f"跳过率: {score_baseline.skip_rate:.1%}")
print(f"综合得分: {score_baseline.composite_score:.1f}/100")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)
print(f"基线配置: {score_baseline.direction_accuracy:.1%} 命中率")
print(f"距离70%准入标准: {0.70 - score_baseline.direction_accuracy:.1%}")
