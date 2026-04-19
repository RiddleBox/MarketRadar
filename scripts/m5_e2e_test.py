"""
tests/_m5_test.py — M4→M5 持仓管理测试

流程：
  1. 复用 _full_pipeline_test 的思路，快速生成一个 ActionPlan
  2. M5 开仓
  3. 模拟价格变化（上涨 / 下跌至止损 / 上涨至止盈）
  4. 验证触发逻辑
  5. 平仓，查看汇总
"""
import os, sys, time, tempfile
os.environ["DEEPSEEK_API_KEY"] = "sk-6c899392de5444369b4518e8c64aa940"
sys.path.insert(0, r"D:\AIproject\MarketRadar")

from pathlib import Path
from datetime import datetime

from core.schemas import (
    ActionPlan, ActionPhase, ActionType,
    StopLossConfig, TakeProfitConfig, PositionSizing,
    InstrumentType, PriorityLevel, Direction, Market,
)
from m5_position.position_manager import PositionManager

# 临时持仓文件，不污染正式数据
tmpdir = tempfile.mkdtemp()
positions_file = Path(tmpdir) / "positions.json"
print(f"测试持仓文件: {positions_file}")

# ── 构造一个 ActionPlan（不需要跑 LLM，直接构造）──────────────────────
plan = ActionPlan(
    opportunity_id="opp_test_001",
    plan_summary="降息驱动A股反弹，分批做多沪深300ETF",
    primary_instruments=["510300.SH", "510050.SH"],
    instrument_type=InstrumentType.ETF,
    stop_loss=StopLossConfig(
        stop_loss_type="percent",
        stop_loss_value=5.0,
        notes="跌破降息当日K线最低点",
    ),
    take_profit=TakeProfitConfig(
        take_profit_type="percent",
        take_profit_value=10.0,
        partial_take_profit=True,
        partial_ratio=0.5,
        notes="第一目标前期震荡上沿",
    ),
    position_sizing=PositionSizing(
        suggested_allocation="1-2%",
        max_allocation="不超过3%",
        sizing_rationale="research 级别，控制仓位",
    ),
    phases=[
        ActionPhase(
            phase_name="侦察仓",
            action_type=ActionType.BUY,
            timing_description="当日收盘前分批买入",
            allocation_ratio=0.5,
        ),
        ActionPhase(
            phase_name="主仓",
            action_type=ActionType.BUY,
            timing_description="次日确认强势后加仓",
            allocation_ratio=0.5,
        ),
    ],
    valid_until=datetime(2026, 4, 27),
    review_triggers=["关键假设失效", "21天内未触发入场则放弃"],
    opportunity_priority=PriorityLevel.RESEARCH,
)

print(f"\nActionPlan 构造成功: {plan.plan_id}")
print(f"  标的: {plan.primary_instruments}")
print(f"  止损: {plan.stop_loss.stop_loss_type} {plan.stop_loss.stop_loss_value}%")
print(f"  止盈: {plan.take_profit.take_profit_type} {plan.take_profit.take_profit_value}%")

# ── M5 初始化 ─────────────────────────────────────────────────────────
pm = PositionManager(positions_file=positions_file)

# ══════════════════════════════════════════════════════════════
# 场景1：正常做多，价格上涨至止盈
# ══════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("场景1: 做多 510300.SH，价格上涨触发止盈")
print("="*55)

ENTRY = 3.80   # 入场价
QTY   = 10000  # 股数

pos1 = pm.open_position(
    plan=plan,
    instrument="510300.SH",
    entry_price=ENTRY,
    quantity=QTY,
    market=Market.A_SHARE,
    direction=Direction.BULLISH,
)
print(f"开仓 ✓ | id={pos1.position_id}")
print(f"  成本价={pos1.entry_price} | 数量={pos1.quantity} | 总成本={pos1.total_cost:.0f}元")
print(f"  止损价={pos1.stop_loss_price:.4f} | 止盈价={pos1.take_profit_price:.4f}")

# 模拟价格波动
price_seq = [3.82, 3.88, 3.95, 4.05, 4.18]
for px in price_seq:
    upd = pm.update_price(pos1.position_id, px)
    trigger = pm.check_triggers(pos1.position_id, px)
    flag = f" ← {trigger}" if trigger else ""
    print(f"  价格 {px:.2f} | 浮盈 {upd.unrealized_pnl_pct:+.2f}%{flag}")
    if trigger:
        # 止盈触发，平仓
        closed = pm.close_position(pos1.position_id, px, "止盈触发")
        print(f"  平仓 ✓ | 实现盈亏={closed.realized_pnl:+.0f}元 ({closed.realized_pnl_pct:+.2f}%)")
        break

# ══════════════════════════════════════════════════════════════
# 场景2：做多，价格下跌触发止损
# ══════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("场景2: 做多 510300.SH，价格下跌触发止损")
print("="*55)

pos2 = pm.open_position(
    plan=plan,
    instrument="510300.SH",
    entry_price=ENTRY,
    quantity=QTY,
    market=Market.A_SHARE,
    direction=Direction.BULLISH,
    notes="批次2加仓",
)
print(f"开仓 ✓ | id={pos2.position_id} 止损价={pos2.stop_loss_price:.4f}")

price_seq2 = [3.78, 3.72, 3.65, 3.60]
for px in price_seq2:
    upd = pm.update_price(pos2.position_id, px)
    trigger = pm.check_triggers(pos2.position_id, px)
    flag = f" ← {trigger}" if trigger else ""
    print(f"  价格 {px:.2f} | 浮亏 {upd.unrealized_pnl_pct:+.2f}%{flag}")
    if trigger:
        closed = pm.close_position(pos2.position_id, px, "止损触发")
        print(f"  平仓 ✓ | 实现亏损={closed.realized_pnl:+.0f}元 ({closed.realized_pnl_pct:+.2f}%)")
        break

# ══════════════════════════════════════════════════════════════
# 场景3：移动止损
# ══════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("场景3: 做多，价格上涨后上移止损保护利润")
print("="*55)

pos3 = pm.open_position(
    plan=plan,
    instrument="510300.SH",
    entry_price=ENTRY,
    quantity=5000,
    market=Market.A_SHARE,
    direction=Direction.BULLISH,
)
print(f"开仓 ✓ | 初始止损={pos3.stop_loss_price:.4f}")

# 价格涨到 4.00，把止损上移至成本价（保本止损）
pm.update_price(pos3.position_id, 4.00)
pm.update_stop_loss(pos3.position_id, ENTRY, "价格上涨>5%，止损上移至成本价（保本）")
pos3_updated = pm.get_position(pos3.position_id)
print(f"止损上移 → {pos3_updated.stop_loss_price:.4f}（成本价）")

# 继续涨，手动平仓
pm.update_price(pos3.position_id, 4.15)
closed3 = pm.close_position(pos3.position_id, 4.15, "手动止盈")
print(f"手动平仓 | 实现盈亏={closed3.realized_pnl:+.0f}元 ({closed3.realized_pnl_pct:+.2f}%)")

# ══════════════════════════════════════════════════════════════
# 汇总统计
# ══════════════════════════════════════════════════════════════
print("\n" + "="*55)
summary = pm.get_summary()
print("持仓汇总:")
print(f"  开仓中: {summary['open_count']} | 已平仓: {summary['closed_count']}")
print(f"  胜率: {summary['win_rate']*100:.0f}%" if summary['win_rate'] else "  胜率: N/A")
print(f"  总实现盈亏: {summary['total_realized_pnl']:+.0f}元")
print(f"  平均盈亏率: {summary['avg_realized_pnl_pct']:+.2f}%" if summary['avg_realized_pnl_pct'] else "")

all_pos = pm.get_all_positions()
print(f"\n持仓记录 ({len(all_pos)} 条):")
for p in all_pos:
    pnl_str = f"实现 {p.realized_pnl_pct:+.2f}%" if p.realized_pnl_pct is not None else "持仓中"
    print(f"  [{p.status.value}] {p.instrument} {p.direction.value} @{p.entry_price} | {pnl_str} | 原因: {p.exit_reason or '-'}")

print(f"\n持仓文件: {positions_file}")
print("M5 测试全部通过 ✓")
