#!/usr/bin/env python3
"""
实时模拟盘演示脚本

使用免费数据源（AKShare）测试完整流程：
  1. 创建 ActionPlan
  2. 开仓
  3. 实时更新价格
  4. 触发止损/止盈
"""
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from core.schemas import (
    ActionPlan, ActionPhase, ActionType, Direction, InstrumentType,
    Market, PositionSizing, PriorityLevel, StopLossConfig, TakeProfitConfig,
)
from m9_paper_trader.paper_trader import PaperTrader
from m9_paper_trader.price_feed import make_price_feed


def create_test_plan(instrument: str, market: Market) -> ActionPlan:
    """创建测试用 ActionPlan"""
    return ActionPlan(
        opportunity_id=f"demo_{instrument}_{int(time.time())}",
        plan_summary=f"BULLISH | {instrument} | Demo",
        primary_instruments=[instrument],
        instrument_type=InstrumentType.STOCK,
        direction=Direction.BULLISH,
        market=market,
        stop_loss=StopLossConfig(
            stop_loss_type="percent",
            stop_loss_value=3.0,  # -3% 止损
            hard_stop=True,
        ),
        take_profit=TakeProfitConfig(
            take_profit_type="percent",
            take_profit_value=5.0,  # +5% 止盈
        ),
        position_sizing=PositionSizing(
            suggested_allocation="10%",
            max_allocation="15%",
            sizing_rationale="demo test",
            suggested_allocation_pct=0.10,
            max_allocation_pct=0.15,
        ),
        phases=[
            ActionPhase(
                phase_name="Phase 1",
                action_type=ActionType.BUY,
                timing_description="immediate",
                allocation_ratio=1.0,
            )
        ],
        valid_until=datetime.now() + timedelta(days=7),
        review_triggers=["7 days"],
        opportunity_priority=PriorityLevel.POSITION,
    )


def main():
    print("=" * 70)
    print("MarketRadar 实时模拟盘演示")
    print("=" * 70)
    print()
    
    # 1. 创建价格数据源（使用免费的 AKShare）
    print("📊 初始化数据源...")
    feed = make_price_feed(mode="composite")  # TuShare → AKShare → YFinance
    print("✓ 数据源就绪（AKShare + YFinance fallback）\n")
    
    # 2. 创建模拟盘
    print("💼 初始化模拟盘...")
    trader = PaperTrader(
        initial_capital=100000.0,  # 10万初始资金
        price_feed=feed,
    )
    print(f"✓ 初始资金: ¥{trader.initial_capital:,.2f}\n")
    
    # 3. 测试标的（A股 ETF，流动性好）
    test_instruments = [
        ("510300.SH", Market.A_SHARE, "沪深300ETF"),
        ("159915.SZ", Market.A_SHARE, "创业板ETF"),
    ]
    
    print("🎯 测试标的:")
    for code, market, name in test_instruments:
        print(f"  - {name} ({code})")
    print()
    
    # 4. 获取当前价格
    print("📈 获取实时行情...")
    positions_to_open = []
    
    for code, market, name in test_instruments:
        snapshot = feed.get_price(code)
        if snapshot and snapshot.last > 0:
            print(f"✓ {name} ({code}): ¥{snapshot.last:.3f}")
            positions_to_open.append((code, market, name, snapshot.last))
        else:
            print(f"✗ {name} ({code}): 无法获取价格")
    
    if not positions_to_open:
        print("\n❌ 无法获取任何标的价格，退出演示")
        return
    
    print()
    
    # 5. 开仓
    print("🔨 开仓...")
    opened_positions = []
    
    for code, market, name, price in positions_to_open:
        plan = create_test_plan(code, market)
        pos = trader.open_from_plan(plan, entry_price=price)
        
        if pos:
            opened_positions.append((pos, name))
            print(f"✓ {name}: {pos.quantity} 股 @ ¥{pos.entry_price:.3f}")
            print(f"  止损: ¥{pos.stop_loss_price:.3f} (-3%)")
            print(f"  止盈: ¥{pos.take_profit_price:.3f} (+5%)")
        else:
            print(f"✗ {name}: 开仓失败")
    
    if not opened_positions:
        print("\n❌ 没有成功开仓的持仓，退出演示")
        return
    
    print()
    
    # 6. 显示持仓状态
    print("📋 当前持仓:")
    for pos, name in opened_positions:
        print(f"  {name}: {pos.quantity} 股 @ ¥{pos.entry_price:.3f}")
    print()
    
    # 7. 模拟价格更新（实际使用中应该定时调用）
    print("🔄 开始监控价格变化...")
    print("   (按 Ctrl+C 退出)\n")
    
    update_count = 0
    try:
        while True:
            update_count += 1
            print(f"--- 更新 #{update_count} ({datetime.now().strftime('%H:%M:%S')}) ---")
            
            # 更新所有持仓
            trader.update_all_positions()
            
            # 检查持仓状态
            active_count = 0
            closed_count = 0
            
            for pos, name in opened_positions:
                current_pos = trader.get_position(pos.position_id)
                if current_pos.status == "OPEN":
                    active_count += 1
                    pnl_pct = current_pos.unrealized_pnl_pct or 0
                    pnl_symbol = "📈" if pnl_pct > 0 else "📉" if pnl_pct < 0 else "➡️"
                    print(f"{pnl_symbol} {name}: ¥{current_pos.current_price:.3f} ({pnl_pct:+.2f}%)")
                else:
                    closed_count += 1
                    print(f"🔒 {name}: 已平仓 ({current_pos.exit_reason})")
            
            print(f"持仓: {active_count} 活跃 / {closed_count} 已平仓")
            
            if active_count == 0:
                print("\n✅ 所有持仓已平仓，演示结束")
                break
            
            print()
            time.sleep(10)  # 每 10 秒更新一次
            
    except KeyboardInterrupt:
        print("\n\n⏸️  演示中断")
    
    # 8. 最终报告
    print("\n" + "=" * 70)
    print("📊 最终报告")
    print("=" * 70)
    
    total_pnl = 0
    for pos, name in opened_positions:
        current_pos = trader.get_position(pos.position_id)
        pnl = current_pos.realized_pnl or current_pos.unrealized_pnl or 0
        total_pnl += pnl
        
        status_icon = "✅" if current_pos.status == "CLOSED" else "⏳"
        print(f"{status_icon} {name}:")
        print(f"   入场: ¥{current_pos.entry_price:.3f}")
        if current_pos.status == "CLOSED":
            print(f"   出场: ¥{current_pos.exit_price:.3f}")
            print(f"   原因: {current_pos.exit_reason}")
        else:
            print(f"   当前: ¥{current_pos.current_price:.3f}")
        print(f"   盈亏: ¥{pnl:+.2f}")
    
    print()
    print(f"总盈亏: ¥{total_pnl:+.2f}")
    print(f"收益率: {(total_pnl / trader.initial_capital * 100):+.2f}%")
    print()


if __name__ == "__main__":
    main()
