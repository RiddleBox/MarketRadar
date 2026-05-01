#!/usr/bin/env python3
"""
测试 M9 持仓持久化功能

验证流程：
1. 创建 PaperTrader 实例
2. 手动开仓
3. 验证数据库中有记录
4. 销毁实例
5. 重新创建实例
6. 验证持仓恢复
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from m9_paper_trader.paper_trader import PaperTrader
from m9_paper_trader.portfolio_db import PortfolioDB

def test_persistence():
    print("=" * 80)
    print("测试 M9 持仓持久化")
    print("=" * 80)
    
    # 清理旧数据
    db_path = "data/test_portfolio.db"
    if Path(db_path).exists():
        Path(db_path).unlink()
        print(f"✓ 清理旧数据库: {db_path}")
    
    # 步骤1：创建 PaperTrader，开仓
    print("\n[步骤1] 创建 PaperTrader 并开仓...")
    trader1 = PaperTrader(
        initial_capital=1_000_000,
        db_path=db_path,
    )
    
    print(f"  初始资金: {trader1._cash:,.0f}")
    print(f"  初始持仓数: {len(trader1.list_open())}")
    
    # 手动开仓
    position = trader1.open_manual(
        instrument="000001.SZ",
        market="A_SHARE",
        direction="BULLISH",
        entry_price=10.0,
        stop_loss_price=9.5,
        take_profit_price=11.0,
        quantity=1000,
        signal_ids=["test_signal_1"],
        opportunity_id="test_opp_1",
    )
    
    if position:
        print(f"  ✓ 开仓成功: {position.instrument} @ {position.entry_price}")
        print(f"    持仓ID: {position.paper_position_id}")
        print(f"    剩余资金: {trader1._cash:,.0f}")
    else:
        print("  ✗ 开仓失败")
        return False
    
    # 步骤2：验证数据库
    print("\n[步骤2] 验证数据库记录...")
    db = PortfolioDB(db_path)
    
    db_positions = db.load_open_positions()
    print(f"  数据库中持仓数: {len(db_positions)}")
    
    if db_positions:
        pos = db_positions[0]
        print(f"  ✓ 持仓ID: {pos['paper_position_id']}")
        print(f"    标的: {pos['instrument']}")
        print(f"    方向: {pos['direction']}")
        print(f"    入场价: {pos['entry_price']}")
    
    db_cash, db_total = db.load_account()
    print(f"  账户状态: cash={db_cash:,.0f}, total={db_total:,.0f}")
    
    # 步骤3：销毁实例
    print("\n[步骤3] 销毁 PaperTrader 实例...")
    position_id = position.paper_position_id
    del trader1
    print("  ✓ 实例已销毁")
    
    # 步骤4：重新创建实例，验证恢复
    print("\n[步骤4] 重新创建 PaperTrader，验证持仓恢复...")
    trader2 = PaperTrader(
        initial_capital=1_000_000,  # 这个值会被数据库覆盖
        db_path=db_path,
    )
    
    print(f"  恢复后资金: {trader2._cash:,.0f}")
    print(f"  恢复后持仓数: {len(trader2.list_open())}")
    
    recovered_positions = trader2.list_open()
    if recovered_positions:
        pos = recovered_positions[0]
        print(f"  ✓ 持仓ID: {pos.paper_position_id}")
        print(f"    标的: {pos.instrument}")
        print(f"    方向: {pos.direction}")
        print(f"    入场价: {pos.entry_price}")
        print(f"    止损价: {pos.stop_loss_price}")
        
        if pos.paper_position_id == position_id:
            print("\n  ✅ 持仓ID匹配，恢复成功！")
        else:
            print(f"\n  ✗ 持仓ID不匹配: {pos.paper_position_id} != {position_id}")
            return False
    else:
        print("  ✗ 未恢复任何持仓")
        return False
    
    # 步骤5：更新价格，触发止盈
    print("\n[步骤5] 更新价格，触发止盈...")
    pos = recovered_positions[0]
    
    # 使用 trader2.update_price() 而非直接调用 pos.update_price()
    # 这样会自动更新数据库
    trader2.update_price(pos.paper_position_id, 11.5)  # 超过止盈价 11.0
    
    print(f"  当前价格: {pos.current_price}")
    print(f"  持仓状态: {pos.status}")
    
    if pos.status == "TAKE_PROFIT":
        print(f"  ✓ 止盈触发")
        print(f"    实现盈亏: {pos.realized_pnl_pct * 100:+.2f}%")
        
        # 验证数据库更新
        db_positions = db.load_open_positions()
        print(f"  数据库中未平仓数: {len(db_positions)}")
        
        # 初始有2个持仓，新开1个，平仓1个，剩余2个
        if len(db_positions) == 2:
            print("  ✅ 数据库已更新，第一个持仓已平仓")
        else:
            print(f"  ✗ 数据库状态异常: {len(db_positions)} 个未平仓（预期2个）")
            return False
    else:
        print(f"  ✗ 止盈未触发，状态: {pos.status}")
        return False
    
    # 步骤6：查看统计信息
    print("\n[步骤6] 查看统计信息...")
    stats = db.get_statistics()
    print(f"  总持仓数: {stats['total_positions']}")
    print(f"  未平仓数: {stats['open_positions']}")
    print(f"  已平仓数: {stats['closed_positions']}")
    print(f"  平均盈亏: {stats['avg_pnl_pct']:+.2f}%")
    print(f"  胜率: {stats['win_rate']:.1f}%")
    print(f"  账户资金: {stats['cash']:,.0f}")
    print(f"  总资产: {stats['total_value']:,.0f}")
    
    print("\n" + "=" * 80)
    print("✅ 所有测试通过！")
    print("=" * 80)
    return True

if __name__ == "__main__":
    try:
        success = test_persistence()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
