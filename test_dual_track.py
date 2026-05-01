"""
测试双轨协同功能（避免重复开仓）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from m9_paper_trader import PaperTrader
from core.schemas import ActionPlan, Direction, Market, StopLossConfig, TakeProfitConfig, PositionSizing


def test_dual_track_coordination():
    """测试双轨协同：同一标的不能重复开仓"""
    print("=" * 60)
    print("测试双轨协同功能")
    print("=" * 60)

    # 初始化模拟盘（使用测试数据库）
    trader = PaperTrader(
        initial_capital=1_000_000,
        db_path="data/test_dual_track.db"
    )

    # 创建测试 ActionPlan
    plan1 = ActionPlan(
        plan_id="plan_track1_001",
        opportunity_id="opp_001",
        market=Market.A_SHARE,
        direction=Direction.BULLISH,
        primary_instruments=["600519.SH"],  # 贵州茅台
        stop_loss=StopLossConfig(stop_loss_type="percent", stop_loss_value=5.0),
        take_profit=TakeProfitConfig(take_profit_type="percent", take_profit_value=10.0),
        position_sizing=PositionSizing(
            suggested_allocation="10%",
            max_allocation="15%",
            sizing_rationale="测试",
            suggested_allocation_pct=0.1
        ),
    )

    plan2 = ActionPlan(
        plan_id="plan_track2_001",
        opportunity_id="opp_002",
        market=Market.A_SHARE,
        direction=Direction.BULLISH,
        primary_instruments=["600519.SH"],  # 同一标的
        stop_loss=StopLossConfig(stop_loss_type="percent", stop_loss_value=5.0),
        take_profit=TakeProfitConfig(take_profit_type="percent", take_profit_value=10.0),
        position_sizing=PositionSizing(
            suggested_allocation="10%",
            max_allocation="15%",
            sizing_rationale="测试",
            suggested_allocation_pct=0.1
        ),
    )

    # 测试1: 轨道1开仓（应该成功）
    print("\n[测试1] 轨道1开仓 600519.SH")
    positions1 = trader.open_from_plan(
        plan=plan1,
        signal_ids=["sig_001"],
        opportunity_id="opp_001",
        entry_price=1800.0,
        prev_close=1800.0,
        signal_confidence=0.8,
    )
    print(f"  开仓结果: {len(positions1)} 个持仓")
    assert len(positions1) == 1, "轨道1应该成功开仓"
    print(f"  持仓ID: {positions1[0].paper_position_id}")

    # 测试2: 轨道2尝试开仓同一标的（应该被拒绝）
    print("\n[测试2] 轨道2尝试开仓 600519.SH（应该被拒绝）")
    positions2 = trader.open_from_plan(
        plan=plan2,
        signal_ids=["sig_002"],
        opportunity_id="opp_002",
        entry_price=1810.0,
        prev_close=1800.0,
        signal_confidence=0.7,
    )
    print(f"  开仓结果: {len(positions2)} 个持仓")
    assert len(positions2) == 0, "轨道2应该被拒绝（标的已存在）"

    # 测试3: 平仓后，轨道2可以开仓
    print("\n[测试3] 平仓后，轨道2可以开仓")
    print(f"  平仓 {positions1[0].paper_position_id}...")
    trader.close_position(
        paper_position_id=positions1[0].paper_position_id,
        exit_price=1850.0,
        reason="TEST_CLOSE"
    )
    print(f"  持仓状态: {positions1[0].status}")

    print(f"  轨道2再次尝试开仓 600519.SH...")
    positions3 = trader.open_from_plan(
        plan=plan2,
        signal_ids=["sig_003"],
        opportunity_id="opp_003",
        entry_price=1850.0,
        prev_close=1850.0,
        signal_confidence=0.75,
    )
    print(f"  开仓结果: {len(positions3)} 个持仓")
    assert len(positions3) == 1, "平仓后应该可以重新开仓"
    print(f"  持仓ID: {positions3[0].paper_position_id}")

    print("\n" + "=" * 60)
    print("✅ 所有测试通过")
    print("=" * 60)


if __name__ == "__main__":
    test_dual_track_coordination()
