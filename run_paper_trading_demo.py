#!/usr/bin/env python3
"""
实时模拟盘演示脚本

使用 Baostock 获取历史价格，测试完整流程：
  1. 创建 ActionPlan
  2. 开仓
  3. 模拟价格更新
  4. 触发止损/止盈
"""

import sys
import os
import time
import random
from datetime import datetime, timedelta, date
from pathlib import Path

if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from core.schemas import (
    ActionPlan,
    ActionPhase,
    ActionType,
    Direction,
    InstrumentType,
    Market,
    PositionSizing,
    PriorityLevel,
    StopLossConfig,
    TakeProfitConfig,
)
from m9_paper_trader.paper_trader import PaperTrader


def get_price_baostock(instrument: str) -> float:
    """通过 Baostock 获取最新收盘价"""
    import baostock as bs

    code = instrument.split(".")[0]
    suffix = instrument.split(".")[-1].upper()

    # 转换 Baostock 格式: 510300.SH -> sh.510300
    bs_prefix = "sh" if suffix == "SH" else "sz"
    bs_code = f"{bs_prefix}.{code}"

    lg = bs.login()
    try:
        end_date = date.today().strftime("%Y-%m-%d")
        start_date = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
        df = bs.query_history_k_data_plus(
            bs_code, "date,close", start_date=start_date, end_date=end_date
        )
        data = df.get_data()
        if data is not None and not data.empty:
            return float(data.iloc[-1]["close"])
    finally:
        bs.logout()
    return 0.0


def create_test_plan(instrument: str, market: Market) -> ActionPlan:
    return ActionPlan(
        opportunity_id=f"demo_{instrument}_{int(time.time())}",
        plan_summary=f"BULLISH | {instrument} | Demo",
        primary_instruments=[instrument],
        instrument_type=InstrumentType.STOCK,
        direction=Direction.BULLISH,
        market=market,
        stop_loss=StopLossConfig(
            stop_loss_type="percent",
            stop_loss_value=3.0,
            hard_stop=True,
        ),
        take_profit=TakeProfitConfig(
            take_profit_type="percent",
            take_profit_value=5.0,
        ),
        position_sizing=PositionSizing(
            suggested_allocation="5%",
            max_allocation="8%",
            sizing_rationale="demo test",
            suggested_allocation_pct=0.05,
            max_allocation_pct=0.08,
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

    print("初始化模拟盘...")
    trader = PaperTrader(initial_capital=1_000_000.0)
    print(f"初始资金: {trader._initial_capital:,.2f}\n")

    test_instruments = [
        ("510300.SH", Market.A_SHARE, "沪深300ETF"),
        ("159915.SZ", Market.A_SHARE, "创业板ETF"),
    ]

    print("测试标的:")
    for code, market, name in test_instruments:
        print(f"  - {name} ({code})")
    print()

    print("获取最近交易日价格 (Baostock)...")
    positions_to_open = []

    for code, market, name in test_instruments:
        price = get_price_baostock(code)
        if price > 0:
            print(f"  {name} ({code}): {price:.3f}")
            positions_to_open.append((code, market, name, price))
        else:
            print(f"  {name} ({code}): 无法获取价格")

    if not positions_to_open:
        print("\n无法获取任何标的价格，退出演示")
        return

    print()
    print("开仓...")
    opened_positions = []

    for code, market, name, price in positions_to_open:
        plan = create_test_plan(code, market)
        positions = trader.open_from_plan(
            plan,
            signal_ids=[f"demo_signal_{code}"],
            opportunity_id=f"demo_opp_{code}",
            entry_price=price,
        )

        if positions:
            for pos in positions:
                opened_positions.append((pos, name))
                print(f"  {name}: {pos.quantity} 股 @ {pos.entry_price:.3f}")
                print(f"    止损: {pos.stop_loss_price:.3f} (-3%)")
                print(f"    止盈: {pos.take_profit_price:.3f} (+5%)")
        else:
            print(f"  {name}: 开仓失败")

    if not opened_positions:
        print("\n没有成功开仓的持仓，退出演示")
        return

    print()
    print("当前持仓:")
    for pos, name in opened_positions:
        print(f"  {name}: {pos.quantity} 股 @ {pos.entry_price:.3f}")
    print()

    print("开始模拟价格变化 (按 Ctrl+C 退出)...")
    print()

    update_count = 0
    max_updates = 30

    try:
        while update_count < max_updates:
            update_count += 1
            print(
                f"--- 更新 #{update_count} ({datetime.now().strftime('%H:%M:%S')}) ---"
            )

            for pos, name in opened_positions:
                current_pos = trader.get(pos.paper_position_id)
                if current_pos and current_pos.status == "OPEN":
                    change = random.uniform(-0.005, 0.005)
                    new_price = current_pos.current_price * (1 + change)
                    trader.update_price(current_pos.paper_position_id, new_price)

                    pnl_pct = current_pos.unrealized_pnl_pct or 0
                    pnl_symbol = "+" if pnl_pct > 0 else ""
                    print(
                        f"  {name}: {current_pos.current_price:.3f} ({pnl_symbol}{pnl_pct * 100:.2f}%)"
                    )

            active = [
                p
                for p, _ in opened_positions
                if trader.get(p.paper_position_id)
                and trader.get(p.paper_position_id).status == "OPEN"
            ]
            closed = [
                p
                for p, _ in opened_positions
                if trader.get(p.paper_position_id)
                and trader.get(p.paper_position_id).status != "OPEN"
            ]
            print(f"持仓: {len(active)} 活跃 / {len(closed)} 已平仓")

            if not active:
                print("\n所有持仓已平仓，演示结束")
                break

            print()
            time.sleep(2)

    except KeyboardInterrupt:
        print("\n\n演示中断")

    print("\n" + "=" * 70)
    print("最终报告")
    print("=" * 70)

    total_pnl = 0
    for pos, name in opened_positions:
        current_pos = trader.get(pos.paper_position_id)
        if current_pos:
            pnl = current_pos.realized_pnl_pct or current_pos.unrealized_pnl_pct or 0
            total_pnl += pnl * (current_pos.entry_price * current_pos.quantity)

            status_icon = "[完成]" if current_pos.status not in ["OPEN"] else "[持仓]"
            print(f"{status_icon} {name}:")
            print(f"   入场: {current_pos.entry_price:.3f}")
            if current_pos.status not in ["OPEN"]:
                print(f"   出场: {current_pos.exit_price:.3f}")
                print(f"   原因: {current_pos.status}")
            else:
                print(f"   当前: {current_pos.current_price:.3f}")
            print(f"   盈亏: {pnl * 100:+.2f}%")

    print()
    print(f"总盈亏: {total_pnl:+.2f}")
    print(f"收益率: {(total_pnl / trader._initial_capital * 100):+.2f}%")
    print()


if __name__ == "__main__":
    main()
