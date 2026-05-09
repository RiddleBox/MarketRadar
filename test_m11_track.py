"""
测试 M11 Agent模拟轨道

流程：
  M11 多Agent模拟 → 生成群体情绪分布 → 转换为洞察信号 → M2存储 → M3判断
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
from m11_agent_sim.agent_network import AgentNetwork
from m11_agent_sim.schemas import MarketInput, PriceContext, SentimentContext, SignalContext
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine

def print_section(title):
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)

def main():
    print_section("M11 Agent模拟轨道测试")

    # Step 1: 创建模拟市场输入
    print("\n[Step 1] 创建模拟市场输入...")

    # 模拟一个政策利好场景 - 家电以旧换新补贴
    market_input = MarketInput(
        timestamp=datetime.now(),
        market="A_SHARE",
        event_description="国家发改委发布家电以旧换新补贴政策，单台最高补贴1000元",
        price=PriceContext(
            instrument="000651.SZ",  # 格力电器
            current_price=35.80,
            price_5d_chg_pct=3.5,
            price_20d_chg_pct=8.2,
            volume_ratio=2.1,
            ma5=34.50,
            ma20=33.20,
            above_ma5=True,
            above_ma20=True
        ),
        sentiment=SentimentContext(
            fear_greed_index=65.0,  # 偏乐观
            sentiment_label="乐观",
            northbound_flow=15.5,  # 北向资金净流入15.5亿
            advance_decline_ratio=0.62,
            weibo_sentiment=0.3,
            hot_sectors=["家电", "消费", "白色家电"]
        ),
        signals=SignalContext(
            recent_signals=[],
            dominant_signal_type="policy",
            avg_intensity=7.0,
            avg_confidence=0.75,
            bullish_count=3,
            bearish_count=0,
            neutral_count=1
        ),
        recent_extreme_move=5.2,
        days_since_extreme=2
    )

    print(f"[OK] 模拟场景：{market_input.event_description}")
    print(f"  - 标的: {market_input.price.instrument}")
    print(f"  - 当前价格: {market_input.price.current_price}")
    print(f"  - 5日涨幅: +{market_input.price.price_5d_chg_pct}%")
    print(f"  - 北向资金: +{market_input.sentiment.northbound_flow}亿")
    print(f"  - 恐贪指数: {market_input.sentiment.fear_greed_index}")

    # Step 2: M11 Agent模拟
    print("\n[Step 2] M11 多Agent模拟...")
    try:
        # 使用规则模式（不需要LLM）
        network = AgentNetwork.from_config_file(
            market="a_share",
            topology="sequential",
            use_llm=False
        )

        print(f"[OK] 初始化AgentNetwork")
        print(f"  - 拓扑: sequential")
        print(f"  - Agent数量: {len(network._agents)}")

        # 运行模拟
        result = network.run(market_input)

        print(f"\n[OK] 模拟完成")
        print(f"  - 群体方向: {result.direction}")
        print(f"  - 置信度: {result.confidence:.2f}")
        print(f"  - 多头概率: {result.bullish_prob:.2%}")
        print(f"  - 空头概率: {result.bearish_prob:.2%}")
        print(f"  - 中性概率: {result.neutral_prob:.2%}")

        # 显示各Agent的输出
        print(f"\n  各Agent观点:")
        for agent_output in result.agent_outputs:
            print(f"    - {agent_output.agent_type}: {agent_output.direction} (置信度 {agent_output.confidence:.2f})")
            if agent_output.reasoning:
                print(f"      理由: {agent_output.reasoning[:80]}...")

    except Exception as e:
        print(f"[X] M11模拟失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: 转换为MarketSignal并存储到M2
    print("\n[Step 3] 转换为MarketSignal并存储到M2...")
    try:
        from core.schemas import MarketSignal, SignalType, Direction, Market, TimeHorizon, SignalLogicFrame

        # 将群体情绪分布转换为信号
        direction_map = {
            "BULLISH": Direction.BULLISH,
            "BEARISH": Direction.BEARISH,
            "NEUTRAL": Direction.NEUTRAL
        }

        signal_direction = direction_map.get(result.direction, Direction.NEUTRAL)

        # 计算强度（基于置信度和概率分布）
        max_prob = max(result.bullish_prob, result.bearish_prob, result.neutral_prob)
        intensity = int(result.confidence * max_prob * 10)

        market_signal = MarketSignal(
            signal_id=f"m11_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            signal_type=SignalType.SENTIMENT,
            signal_label=f"多Agent群体观点: {result.direction}",
            description=f"模拟{len(result.agent_outputs)}个市场参与者对'{market_input.event_description}'的反应",
            evidence_text=f"多头{result.bullish_prob:.1%} | 空头{result.bearish_prob:.1%} | 中性{result.neutral_prob:.1%}",
            affected_markets=[Market.A_SHARE],
            affected_instruments=[market_input.price.instrument],
            signal_direction=signal_direction,
            event_time=datetime.now(),
            collected_time=datetime.now(),
            time_horizon=TimeHorizon.SHORT,
            intensity_score=intensity,
            confidence_score=int(result.confidence * 10),
            timeliness_score=9,
            source_type="market_monitor",
            source_ref=f"M11_AgentNetwork_{market_input.event_description[:20]}",
            logic_frame=SignalLogicFrame(
                what_changed=market_input.event_description,
                change_direction=result.direction,
                affects=market_input.sentiment.hot_sectors,
                why_matters=f"群体共识置信度{result.confidence:.0%}"
            ),
            batch_id=f"m11_test_{datetime.now().strftime('%Y%m%d_%H%M')}"
        )

        store = SignalStore()
        store.save([market_signal])
        print(f"[OK] Agent模拟信号已存储到M2")

    except Exception as e:
        print(f"[X] M2存储失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: M3判断（使用Agent模拟信号）
    print("\n[Step 4] M3判断（使用Agent模拟信号）...")
    try:
        # 查询最近的信号
        recent_signals = store.query(
            markets=[Market.A_SHARE],
            limit=20,
            lookback_days=1
        )

        print(f"[OK] 查询到 {len(recent_signals)} 个最近信号")

        # 使用M3判断
        judge = JudgmentEngine()
        opportunities = judge.judge(recent_signals)

        print(f"[OK] 生成 {len(opportunities)} 个机会")

        for i, opp in enumerate(opportunities, 1):
            print(f"\n机会 {i}: {opp.opportunity_title}")
            print(f"  优先级: {opp.priority_level.value}")
            print(f"  评分: {opp.opportunity_score.overall_score:.1f}/10")
            print(f"  置信度: {opp.opportunity_score.confidence_score:.2f}")
            if opp.target_instruments:
                print(f"  标的: {opp.target_instruments[:3]}")

    except Exception as e:
        print(f"[X] M3判断失败: {e}")
        import traceback
        traceback.print_exc()

    print_section("M11 轨道测试完成")

if __name__ == "__main__":
    main()
