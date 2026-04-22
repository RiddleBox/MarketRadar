"""
测试M3推理引擎

验证推理能力是否正常工作
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schemas import MarketSignal, SignalType, Market, Direction, TimeHorizon, SourceType, SignalLogicFrame
from m3_judgment.judgment_engine import JudgmentEngine
from m2_storage.signal_store import SignalStore


def create_test_signals() -> list[MarketSignal]:
    """创建测试信号：模拟降准前的信号组合"""

    now = datetime.now()

    signals = [
        # Signal 1: 政策表态
        MarketSignal(
            signal_id="test_signal_001",
            signal_type=SignalType.POLICY,
            signal_label="国务院常务会议：适时降准",
            description="国务院常务会议提到'加大宏观调控力度，适时降准，保持流动性合理充裕'",
            evidence_text="会议强调要加大宏观政策调控力度，适时降准，保持流动性合理充裕",
            affected_markets=[Market.A_SHARE],
            affected_instruments=["510300.SH", "510050.SH"],
            signal_direction=Direction.BULLISH,
            event_time=now - timedelta(days=10),
            collected_time=now - timedelta(days=10),
            time_horizon=TimeHorizon.SHORT,
            intensity_score=9,
            confidence_score=9,
            timeliness_score=9,
            source_type=SourceType.NEWS,
            source_ref="新华社",
            logic_frame=SignalLogicFrame(
                what_changed="政策表态明确提到降准",
                change_direction=Direction.BULLISH,
                affects=["流动性", "风险偏好"]
            )
        ),

        # Signal 2: 经济数据
        MarketSignal(
            signal_id="test_signal_002",
            signal_type=SignalType.MACRO,
            signal_label="8月CPI同比0.6%，通缩压力显现",
            description="8月CPI同比0.6%，PPI同比-1.8%，通缩压力持续",
            evidence_text="统计局数据显示8月CPI同比0.6%，PPI同比-1.8%",
            affected_markets=[Market.A_SHARE],
            affected_instruments=[],
            signal_direction=Direction.BEARISH,
            event_time=now - timedelta(days=12),
            collected_time=now - timedelta(days=12),
            time_horizon=TimeHorizon.MEDIUM,
            intensity_score=8,
            confidence_score=9,
            timeliness_score=8,
            source_type=SourceType.MARKET_DATA,
            source_ref="统计局",
            logic_frame=SignalLogicFrame(
                what_changed="通缩压力加大",
                change_direction=Direction.BEARISH,
                affects=["货币政策", "企业盈利"]
            )
        ),

        # Signal 3: 市场传闻
        MarketSignal(
            signal_id="test_signal_003",
            signal_type=SignalType.SENTIMENT,
            signal_label="券商预测降准概率80%",
            description="多家券商研报预测央行将在2周内降准，概率80%",
            evidence_text="中信证券、华泰证券等多家券商研报预测降准概率80%",
            affected_markets=[Market.A_SHARE],
            affected_instruments=[],
            signal_direction=Direction.BULLISH,
            event_time=now - timedelta(days=5),
            collected_time=now - timedelta(days=5),
            time_horizon=TimeHorizon.SHORT,
            intensity_score=7,
            confidence_score=7,
            timeliness_score=9,
            source_type=SourceType.NEWS,
            source_ref="财联社",
            logic_frame=SignalLogicFrame(
                what_changed="市场预期升温",
                change_direction=Direction.BULLISH,
                affects=["市场情绪", "资金流向"]
            )
        ),
    ]

    return signals


def main():
    """测试推理引擎"""
    print("=" * 60)
    print("测试M3推理引擎")
    print("=" * 60)
    print()

    # Create test signals
    signals = create_test_signals()
    print(f"创建测试信号: {len(signals)} 条")
    for s in signals:
        print(f"  - {s.signal_label}")
    print()

    # Initialize judgment engine
    print("初始化判断引擎...")
    engine = JudgmentEngine()
    print()

    # Test inference
    print("=" * 60)
    print("测试推理能力")
    print("=" * 60)
    print()

    print("1. 测试因果链推理 (_infer_future_events)")
    inferred_events = engine._infer_future_events(signals)
    print(f"   推理结果: {len(inferred_events)} 个未来事件")
    for event in inferred_events:
        print(f"   - {event.event_description}")
        print(f"     概率: {event.probability:.0%}, 时间窗口: {event.time_window}")
        print(f"     推理依据: {event.reasoning[:100]}...")
    print()

    print("2. 测试历史案例检索 (_retrieve_similar_cases)")
    similar_cases = engine._retrieve_similar_cases(signals, limit=3)
    print(f"   检索结果: {len(similar_cases)} 个相似案例")
    for case in similar_cases:
        print(f"   - {case.case_id} ({case.date_range_start.date()} ~ {case.date_range_end.date()})")
        print(f"     经验教训: {case.lessons[:100]}...")
    print()

    print("3. 测试完整判断流程 (judge)")
    opportunities = engine.judge(signals, batch_id="test_batch_001")
    print(f"   判断结果: {len(opportunities)} 个机会")
    for opp in opportunities:
        print(f"   - {opp.opportunity_title}")
        print(f"     优先级: {opp.priority_level}")
        print(f"     推理事件: {len(opp.inferred_events)} 个")
        print(f"     支撑案例: {len(opp.supporting_cases)} 个")
        print(f"     机会论述: {opp.opportunity_thesis[:150]}...")
    print()

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
