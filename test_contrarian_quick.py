"""
快速验证脚本：检查 ContrarianAgent 是否生效

运行方式：
cd /mnt/d/AIProjects/MarketRadar
python test_contrarian_quick.py
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

from m11_agent_sim.sentiment_provider import DecorrelatedSentimentProvider
from m11_agent_sim.schemas import MarketInput, SignalContext
from m11_agent_sim.agents.contrarian_agent import ContrarianAgent
from m11_agent_sim.agent_network import AgentNetwork
from datetime import datetime

print("=" * 60)
print("ContrarianAgent 快速验证")
print("=" * 60)

provider = DecorrelatedSentimentProvider()

# 测试关键事件的情绪数据
events = [
    ("2024-09-30", "9-30 牛市情绪爆发"),
    ("2024-11-08", "11-08 万亿国债"),
    ("2024-12-12", "12-12 经济工作会议"),
]

print("\n1. 情绪数据检查：")
for date_str, desc in events:
    sent = provider.get_sentiment(date_str, 'BULLISH', 0.0)
    market_input = MarketInput(
        timestamp=datetime.strptime(date_str, "%Y-%m-%d"),
        market='A_SHARE',
        sentiment=sent,
        signals=SignalContext(bullish_count=5, bearish_count=1, avg_intensity=7.0)
    )
    should_boost = ContrarianAgent.should_boost_weight(market_input)
    print(f"  {desc}: FG={sent.fear_greed_index:.1f}, should_boost={should_boost}")

print("\n2. ContrarianAgent 单独测试：")
agent = ContrarianAgent()
for date_str, desc in events:
    sent = provider.get_sentiment(date_str, 'BULLISH', 0.0)
    market_input = MarketInput(
        timestamp=datetime.strptime(date_str, "%Y-%m-%d"),
        market='A_SHARE',
        sentiment=sent,
        signals=SignalContext(bullish_count=5, bearish_count=1, avg_intensity=7.0)
    )
    output = agent.analyze(market_input, upstream_context=[])
    print(f"  {desc}: {output.direction} (多{output.bullish_prob:.0%}/空{output.bearish_prob:.0%}) 置信{output.confidence:.0%}")
    print(f"    推理: {output.reasoning}")

print("\n3. AgentNetwork 完整测试：")
network = AgentNetwork._default_a_share()
print(f"  Agent 列表: {[a.config.agent_type for a in network._agents]}")
print(f"  ContrarianAgent 在列表中: {'contrarian' in [a.config.agent_type for a in network._agents]}")

for date_str, desc in events:
    sent = provider.get_sentiment(date_str, 'BULLISH', 0.0)
    market_input = MarketInput(
        timestamp=datetime.strptime(date_str, "%Y-%m-%d"),
        market='A_SHARE',
        event_description=desc,
        sentiment=sent,
        signals=SignalContext(bullish_count=5, bearish_count=1, avg_intensity=7.0)
    )
    dist = network.run(market_input)
    print(f"\n  {desc}:")
    print(f"    方向: {dist.direction} (多{dist.bullish_prob:.0%}/空{dist.bearish_prob:.0%}/震{dist.neutral_prob:.0%})")
    print(f"    置信: {dist.confidence:.0%}, 强度: {dist.intensity:.1f}")
    print(f"    Agent 输出:")
    for out in dist.agent_outputs:
        print(f"      {out.agent_name}: {out.direction} 置信{out.confidence:.0%}")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
