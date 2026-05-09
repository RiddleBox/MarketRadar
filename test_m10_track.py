"""
测试 M10 情绪追踪轨道

流程：
  M10 情绪采集 → 生成情绪信号 → M2 存储 → M3 判断（情绪作为辅助）
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
from m10_sentiment.sentiment_engine import SentimentEngine
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from m4_action.action_designer import ActionDesigner

def print_section(title):
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)

def main():
    print_section("M10 情绪追踪轨道测试")

    # Step 1: M10 采集情绪数据
    print("\n[Step 1] M10 情绪采集...")
    engine = SentimentEngine()

    try:
        sentiment_signal = engine.run(
            batch_id=f"test_m10_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            save_snapshot=True
        )

        if sentiment_signal:
            print(f"[OK] 生成情绪信号")
            print(f"  - 信号ID: {sentiment_signal.signal_id}")
            print(f"  - 标签: {sentiment_signal.signal_label}")
            print(f"  - 恐贪指数: {sentiment_signal.fear_greed_index:.1f}")
            print(f"  - 情绪标签: {sentiment_signal.sentiment_label}")
            print(f"  - 方向: {sentiment_signal.signal_direction}")
            print(f"  - 强度: {sentiment_signal.intensity_score:.1f}")
            print(f"  - 置信度: {sentiment_signal.confidence_score:.2f}")
            if sentiment_signal.hot_sectors:
                print(f"  - 热门板块: {', '.join(sentiment_signal.hot_sectors[:3])}")
        else:
            print("[X] 情绪采集失败")
            return

    except Exception as e:
        print(f"[X] M10 采集失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: 转换为 MarketSignal 并存储到 M2
    print("\n[Step 2] 转换为 MarketSignal 并存储到 M2...")
    try:
        from core.schemas import MarketSignal, SignalType, Direction, Market, TimeHorizon, SignalLogicFrame

        # 将 SentimentSignalData 转换为 MarketSignal
        # sentiment_signal.signal_direction 已经是字符串，需要转换为 Direction enum
        direction_str = sentiment_signal.signal_direction
        if isinstance(direction_str, str):
            direction = Direction[direction_str.upper()]
        else:
            direction = direction_str

        market_signal = MarketSignal(
            signal_id=sentiment_signal.signal_id,
            signal_type=SignalType.SENTIMENT,
            signal_label=sentiment_signal.signal_label,
            description=sentiment_signal.description,
            evidence_text=sentiment_signal.evidence_text,
            affected_markets=[Market.A_SHARE],
            affected_instruments=sentiment_signal.affected_instruments or [],
            signal_direction=direction,
            event_time=sentiment_signal.event_time,
            collected_time=datetime.now(),
            time_horizon=TimeHorizon.SHORT,
            intensity_score=int(sentiment_signal.intensity_score),
            confidence_score=int(min(10, sentiment_signal.confidence_score)),  # 钳制到1-10
            timeliness_score=int(sentiment_signal.timeliness_score),
            source_type=sentiment_signal.source_type,
            source_ref=f"M10_sentiment_{sentiment_signal.event_time.strftime('%Y%m%d_%H%M')}",
            logic_frame=SignalLogicFrame(
                what_changed="市场情绪",
                change_direction=direction_str,
                affects=["市场整体"],
                why_matters=f"恐贪指数{sentiment_signal.fear_greed_index:.0f}，{sentiment_signal.sentiment_label}"
            ),
            batch_id=sentiment_signal.batch_id
        )

        store = SignalStore()
        store.save([market_signal])
        print(f"[OK] 情绪信号已存储到 M2")

    except Exception as e:
        print(f"[X] M2 存储失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: M3 判断（情绪信号作为辅助）
    print("\n[Step 3] M3 判断（情绪信号作为辅助）...")
    try:
        # 查询最近的信号（包括情绪信号）
        recent_signals = store.query(
            markets=[Market.A_SHARE],
            limit=20,
            lookback_days=1
        )

        print(f"[OK] 查询到 {len(recent_signals)} 个最近信号")

        # 统计信号类型
        signal_types = {}
        for sig in recent_signals:
            sig_type = sig.signal_type.value
            signal_types[sig_type] = signal_types.get(sig_type, 0) + 1

        print(f"  信号类型分布: {signal_types}")

        # 使用 M3 判断
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

            # 检查是否使用了情绪信号
            related_signal_ids = opp.related_signals if hasattr(opp, 'related_signals') else []
            sentiment_count = sum(1 for sig_id in related_signal_ids if 'sent_' in sig_id)
            if sentiment_count > 0:
                print(f"  [!] 使用了 {sentiment_count} 个情绪信号作为辅助")

    except Exception as e:
        print(f"[X] M3 判断失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: M4 行动设计（可选）
    if opportunities:
        print("\n[Step 4] M4 行动设计...")
        try:
            designer = ActionDesigner()
            plan = designer.design(opportunities[0])

            print(f"[OK] 生成行动计划: {plan.plan_id}")
            print(f"  - 止损: {plan.stop_loss_pct:.1f}%")
            print(f"  - 止盈: {plan.take_profit_pct:.1f}%")
            print(f"  - 仓位: {plan.position_size_pct:.1f}%")

        except Exception as e:
            print(f"[X] M4 设计失败: {e}")

    print_section("M10 轨道测试完成")

if __name__ == "__main__":
    main()
