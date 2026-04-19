"""
pipeline/position_bridge.py — M4→M5 桥接：从 ActionPlan 开立持仓

M4 输出 ActionPlan，M5 需要 Position。此模块负责衔接。
"""
from __future__ import annotations

import logging
from typing import List, Optional

from core.schemas import ActionPlan, Direction, Market, Position
from m5_position.position_manager import PositionManager

logger = logging.getLogger(__name__)

DEFAULT_TOTAL_CAPITAL = 1_000_000


def open_positions_from_plan(
    plan: ActionPlan,
    entry_price: float,
    total_capital: float = DEFAULT_TOTAL_CAPITAL,
    market: Optional[Market] = None,
    direction: Optional[Direction] = None,
    pm: Optional[PositionManager] = None,
) -> List[Position]:
    """从 ActionPlan 开立持仓。

    为 plan.primary_instruments 中的每个标的开立一个 Position。
    仓位由 plan.position_sizing 的数值字段决定。

    Args:
        plan: M4 输出的行动计划
        entry_price: 入场价格（需要外部提供，来自价格数据）
        total_capital: 总资金规模（用于计算数量）
        market: 覆盖 plan.market
        direction: 覆盖 plan.direction
        pm: 可选的 PositionManager 实例

    Returns:
        开立的 Position 列表
    """
    if pm is None:
        pm = PositionManager()

    dir_ = direction or plan.direction
    mkt = market or plan.market

    max_pct = plan.position_sizing.max_allocation_pct or 0.05
    per_instrument_pct = max_pct / max(len(plan.primary_instruments), 1)

    opened = []
    for instrument in plan.primary_instruments:
        position_value = total_capital * per_instrument_pct
        quantity = position_value / entry_price if entry_price > 0 else 0

        if quantity <= 0:
            logger.warning(f"[Bridge] {instrument} quantity=0, skip")
            continue

        pos = pm.open_position(
            plan=plan,
            instrument=instrument,
            entry_price=entry_price,
            quantity=quantity,
            market=mkt,
            instrument_type=plan.instrument_type,
            direction=dir_,
        )
        opened.append(pos)
        logger.info(
            f"[Bridge] opened {instrument} | dir={dir_.value} | "
            f"qty={quantity:.0f} | sl={pos.stop_loss_price:.3f} | tp={pos.take_profit_price:.3f}"
        )

    return opened
