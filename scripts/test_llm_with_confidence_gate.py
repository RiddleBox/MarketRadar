"""
测试 LLM 模式 + DecorrelatedProvider + 置信度门控

对比：
  1. Rule + decorrelated + min_conf=0.50 (Iter 11.5 基线: 61.7%)
  2. LLM + decorrelated + min_conf=0.50 (本次测试)
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

# 测试1: Rule + decorrelated + 0.50 gate (基线)
print("=" * 60)
print("测试1: Rule + decorrelated + min_conf=0.50 (基线)")
print("=" * 60)
network_rule = AgentNetwork._default_a_share(use_llm=False, min_confidence=0.50)
calibrator_rule = HistoricalCalibrator(network=network_rule)
score_rule = calibrator_rule.calibrate(events, persist=False)
print(f"方向命中率: {score_rule.direction_accuracy:.1%}")
print(f"选择性准确率: {score_rule.selective_accuracy:.1%} ({score_rule.selective_n}/{score_rule.total_events})")
print(f"跳过率: {score_rule.skip_rate:.1%}")
print(f"综合得分: {score_rule.composite_score:.1f}")

# 测试2: LLM + decorrelated + 0.50 gate
print("\n" + "=" * 60)
print("测试2: LLM + decorrelated + min_conf=0.50")
print("=" * 60)
print("注意: LLM 模式需要 API 调用，约需 5-10 分钟...")

try:
    from core.llm_client import LLMClient
    llm_client = LLMClient()

    network_llm = AgentNetwork._default_a_share(
        use_llm=True,
        llm_client=llm_client,
        min_confidence=0.50
    )
    calibrator_llm = HistoricalCalibrator(network=network_llm)
    score_llm = calibrator_llm.calibrate(events, persist=False)

    print(f"方向命中率: {score_llm.direction_accuracy:.1%}")
    print(f"选择性准确率: {score_llm.selective_accuracy:.1%} ({score_llm.selective_n}/{score_llm.total_events})")
    print(f"跳过率: {score_llm.skip_rate:.1%}")
    print(f"综合得分: {score_llm.composite_score:.1f}")

    # 对比
    print("\n" + "=" * 60)
    print("对比结果")
    print("=" * 60)
    print(f"方向命中率提升: {score_llm.direction_accuracy - score_rule.direction_accuracy:+.1%}")
    print(f"选择性准确率提升: {score_llm.selective_accuracy - score_rule.selective_accuracy:+.1%}")
    print(f"跳过率差异: {score_llm.skip_rate - score_rule.skip_rate:+.1%}")

except Exception as e:
    print(f"LLM 模式测试失败: {e}")
    print("可能原因: LLM API 不可用或配置问题")
    print("建议: 检查 config/llm_config.yaml 和 .env 配置")
