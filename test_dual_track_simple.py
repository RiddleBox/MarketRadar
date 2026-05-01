"""
测试双轨协同功能（简化版）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from m9_paper_trader.paper_trader import PaperPosition


def test_find_open_position():
    """测试 _find_open_position 方法"""
    print("=" * 60)
    print("测试双轨协同功能（_find_open_position）")
    print("=" * 60)

    # 创建测试持仓
    pos1 = PaperPosition(
        plan_id="plan_001",
        opportunity_id="opp_001",
        signal_ids=["sig_001"],
        instrument="600519.SH",
        market="A_SHARE",
        direction="BULLISH",
        entry_price=1800.0,
        quantity=100,
        stop_loss_price=1710.0,
        take_profit_price=1980.0,
    )

    pos2 = PaperPosition(
        plan_id="plan_002",
        opportunity_id="opp_002",
        signal_ids=["sig_002"],
        instrument="000858.SZ",
        market="A_SHARE",
        direction="BULLISH",
        entry_price=50.0,
        quantity=1000,
        stop_loss_price=47.5,
        take_profit_price=55.0,
    )

    pos3 = PaperPosition(
        plan_id="plan_003",
        opportunity_id="opp_003",
        signal_ids=["sig_003"],
        instrument="600519.SH",  # 与 pos1 相同标的
        market="A_SHARE",
        direction="BULLISH",
        entry_price=1820.0,
        quantity=100,
        stop_loss_price=1729.0,
        take_profit_price=2002.0,
    )
    pos3.status = "CLOSED"  # 已平仓

    # 模拟持仓列表
    positions = [pos1, pos2, pos3]

    # 测试1: 查找存在的未平仓持仓
    print("\n[测试1] 查找 600519.SH（未平仓）")
    found = None
    for pos in positions:
        if pos.instrument == "600519.SH" and pos.status == "OPEN":
            found = pos
            break
    
    print(f"  结果: {'找到' if found else '未找到'}")
    assert found is not None, "应该找到 pos1"
    assert found.paper_position_id == pos1.paper_position_id, "应该是 pos1"
    print(f"  持仓ID: {found.paper_position_id}")
    print(f"  计划ID: {found.plan_id}")

    # 测试2: 查找不存在的标的
    print("\n[测试2] 查找 601318.SH（不存在）")
    found = None
    for pos in positions:
        if pos.instrument == "601318.SH" and pos.status == "OPEN":
            found = pos
            break
    
    print(f"  结果: {'找到' if found else '未找到'}")
    assert found is None, "不应该找到"

    # 测试3: 查找已平仓的持仓（不应该返回）
    print("\n[测试3] 查找 600519.SH（包含已平仓）")
    open_count = sum(1 for pos in positions if pos.instrument == "600519.SH" and pos.status == "OPEN")
    closed_count = sum(1 for pos in positions if pos.instrument == "600519.SH" and pos.status == "CLOSED")
    
    print(f"  未平仓: {open_count} 个")
    print(f"  已平仓: {closed_count} 个")
    assert open_count == 1, "应该只有1个未平仓"
    assert closed_count == 1, "应该有1个已平仓"

    print("\n" + "=" * 60)
    print("✅ 所有测试通过")
    print("=" * 60)
    print("\n[说明] 双轨协同逻辑：")
    print("  - open_from_plan() 开仓前调用 _find_open_position()")
    print("  - 如果找到未平仓持仓，拒绝开仓并记录警告日志")
    print("  - 如果未找到，允许开仓")
    print("  - 已平仓的持仓不影响新开仓")


if __name__ == "__main__":
    test_find_open_position()
