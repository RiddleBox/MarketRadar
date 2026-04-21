"""
m5_position/position_manager.py — 持仓管理器

职责：
  - 建立/跟踪/关闭持仓
  - 检查止损/止盈触发
  - 持久化持仓记录

设计原则见 PRINCIPLES.md：用规则替代情绪，机械执行替代临时判断。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from core.schemas import (
    ActionPlan,
    Direction,
    InstrumentType,
    Market,
    Position,
    PositionStatus,
    PositionUpdate,
)

logger = logging.getLogger(__name__)

POSITIONS_FILE = Path(__file__).parent.parent / "data" / "positions" / "positions.json"


class PositionManager:
    """持仓管理器

    持仓数据持久化到 data/positions/positions.json。
    每次操作后自动保存，防止数据丢失。
    """

    def __init__(self, positions_file: Optional[Path] = None):
        self.positions_file = positions_file or POSITIONS_FILE
        self.positions_file.parent.mkdir(parents=True, exist_ok=True)
        self._positions: Dict[str, Position] = {}
        self._load()

    # ------------------------------------------------------------------
    # 核心操作
    # ------------------------------------------------------------------

    def open_position(
        self,
        plan: ActionPlan,
        instrument: str,
        entry_price: float,
        quantity: float,
        market: Market = Market.A_SHARE,
        instrument_type: InstrumentType = InstrumentType.STOCK,
        direction: Direction = Direction.BULLISH,
        notes: Optional[str] = None,
    ) -> Position:
        """开仓：基于 ActionPlan 建立新持仓

        Args:
            plan: M4 输出的行动计划
            instrument: 实际操作标的代码（如 510300.SH）
            entry_price: 实际入场价格
            quantity: 买入数量（股/手）
            market: 所在市场
            instrument_type: 标的类型
            direction: 做多 / 做空
            notes: 备注

        Returns:
            新建的 Position 对象
        """
        now = datetime.now()
        total_cost = entry_price * quantity

        # 计算止损价（按止损百分比推算）
        sl = plan.stop_loss
        if sl.stop_loss_price is not None:
            stop_loss_price = sl.stop_loss_price
        elif sl.stop_loss_type == "percent":
            pct = sl.stop_loss_value / 100.0
            stop_loss_price = (
                entry_price * (1 - pct) if direction == Direction.BULLISH
                else entry_price * (1 + pct)
            )
        else:
            # ATR 或其他类型：先用默认 5%
            stop_loss_price = entry_price * 0.95

        # 计算止盈价
        tp = plan.take_profit
        if tp.take_profit_price is not None:
            take_profit_price = tp.take_profit_price
        elif tp.take_profit_type == "percent":
            pct = tp.take_profit_value / 100.0
            take_profit_price = (
                entry_price * (1 + pct) if direction == Direction.BULLISH
                else entry_price * (1 - pct)
            )
        else:
            take_profit_price = None

        position = Position(
            plan_id=plan.plan_id,
            opportunity_id=plan.opportunity_id,
            instrument=instrument,
            instrument_type=instrument_type,
            market=market,
            direction=direction,
            entry_price=entry_price,
            entry_time=now,
            quantity=quantity,
            total_cost=total_cost,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            status=PositionStatus.OPEN,
            notes=notes,
        )

        self._positions[position.position_id] = position
        self._save()

        logger.info(
            f"[M5] 开仓 | id={position.position_id} {instrument} "
            f"{direction.value} @{entry_price} x{quantity} "
            f"止损={stop_loss_price:.4f} 止盈={take_profit_price}"
        )
        return position

    def update_price(self, position_id: str, current_price: float) -> PositionUpdate:
        """更新当前价格，记录浮盈快照

        Returns:
            PositionUpdate 记录
        """
        pos = self._get_open(position_id)

        pnl = pos.current_pnl(current_price)
        pnl_pct = pos.current_pnl_pct(current_price)

        update = PositionUpdate(
            position_id=position_id,
            current_price=current_price,
            unrealized_pnl=pnl,
            unrealized_pnl_pct=pnl_pct,
            stop_loss_price=pos.stop_loss_price,
            take_profit_price=pos.take_profit_price,
            notes=f"价格更新 @{current_price:.4f} | 浮盈={pnl_pct:+.2f}%",
        )
        pos.updates.append(update)
        self._save()
        return update

    def check_triggers(self, position_id: str, current_price: float) -> Optional[str]:
        """检查止损/止盈是否触发

        Args:
            current_price: 当前最新价格

        Returns:
            触发信息字符串，None 表示未触发
        """
        pos = self._get_open(position_id)
        pnl_pct = pos.current_pnl_pct(current_price)

        # 止损检查
        if pos.stop_loss_price is not None:
            if pos.direction == Direction.BULLISH and current_price <= pos.stop_loss_price:
                return (
                    f"【止损触发】{pos.instrument} 当前价 {current_price:.4f} ≤ 止损价 {pos.stop_loss_price:.4f}，"
                    f"浮亏 {abs(pnl_pct):.2f}%，请立即执行平仓。"
                )
            elif pos.direction == Direction.BEARISH and current_price >= pos.stop_loss_price:
                return (
                    f"【止损触发】{pos.instrument} 当前价 {current_price:.4f} ≥ 止损价 {pos.stop_loss_price:.4f}，"
                    f"浮亏 {abs(pnl_pct):.2f}%，请立即执行平仓。"
                )

        # 止盈检查
        if pos.take_profit_price is not None:
            if pos.direction == Direction.BULLISH and current_price >= pos.take_profit_price:
                return (
                    f"【止盈触发】{pos.instrument} 当前价 {current_price:.4f} ≥ 止盈价 {pos.take_profit_price:.4f}，"
                    f"浮盈 {pnl_pct:.2f}%，建议执行止盈。"
                )
            elif pos.direction == Direction.BEARISH and current_price <= pos.take_profit_price:
                return (
                    f"【止盈触发】{pos.instrument} 当前价 {current_price:.4f} ≤ 止盈价 {pos.take_profit_price:.4f}，"
                    f"浮盈 {pnl_pct:.2f}%，建议执行止盈。"
                )

        return None

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str,
    ) -> Position:
        """平仓

        Args:
            position_id: 持仓 ID
            exit_price: 实际平仓价格
            reason: 平仓原因

        Returns:
            已关闭的 Position 对象
        """
        pos = self._get_open(position_id)
        now = datetime.now()

        if pos.direction == Direction.BULLISH:
            realized_pnl = (exit_price - pos.entry_price) * pos.quantity
            realized_pnl_pct = (exit_price - pos.entry_price) / pos.entry_price * 100
        else:
            realized_pnl = (pos.entry_price - exit_price) * pos.quantity
            realized_pnl_pct = (pos.entry_price - exit_price) / pos.entry_price * 100

        pos.status = PositionStatus.CLOSED
        pos.exit_price = exit_price
        pos.exit_time = now
        pos.exit_reason = reason
        pos.realized_pnl = realized_pnl
        pos.realized_pnl_pct = realized_pnl_pct

        # 最后一次 update 记录
        pos.updates.append(PositionUpdate(
            position_id=position_id,
            current_price=exit_price,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            notes=f"平仓 | 原因={reason} | 实现盈亏={realized_pnl_pct:+.2f}%",
        ))

        self._save()

        emoji = "✅" if realized_pnl >= 0 else "❌"
        logger.info(
            f"[M5] 平仓 {emoji} | id={position_id} {pos.instrument} "
            f"原因={reason} 盈亏={realized_pnl_pct:+.2f}%"
        )
        return pos

    def update_stop_loss(
        self,
        position_id: str,
        new_stop: float,
        reason: str = "",
        new_plan: Optional[object] = None,
    ) -> Position:
        """更新止损价（移动止损）。

        根据 M5 PRINCIPLES.md：不修改 M4 设定的止损位，除非有新的 ActionPlan 覆盖。
        调用此方法时必须提供新的 ActionPlan 作为依据，否则记录 WARNING 日志。
        """
        if new_plan is None:
            logger.warning(
                f"[M5] 止损更新未提供新 ActionPlan | id={position_id} "
                f"{reason} — 违反 PRINCIPLES: 不修改 M4 设定的止损位"
            )
        pos = self._get_open(position_id)
        old_stop = pos.stop_loss_price
        pos.stop_loss_price = new_stop
        pos.updates.append(PositionUpdate(
            position_id=position_id,
            current_price=new_stop,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            stop_loss_price=new_stop,
            notes=f"止损更新 {old_stop:.4f} → {new_stop:.4f} | {reason} | plan={'yes' if new_plan else 'no'}",
        ))
        self._save()
        logger.info(f"[M5] 止损更新 | id={position_id} {old_stop:.4f} → {new_stop:.4f}")
        return pos

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_position(self, position_id: str) -> Optional[Position]:
        return self._positions.get(position_id)

    def get_all_positions(self) -> List[Position]:
        return list(self._positions.values())

    def get_open_positions(self) -> List[Position]:
        return [p for p in self._positions.values() if p.status == PositionStatus.OPEN]

    def get_closed_positions(self) -> List[Position]:
        return [p for p in self._positions.values() if p.status == PositionStatus.CLOSED]

    def get_summary(self) -> dict:
        """持仓摘要统计"""
        open_pos = self.get_open_positions()
        closed_pos = self.get_closed_positions()

        win_trades = [p for p in closed_pos if p.realized_pnl and p.realized_pnl > 0]
        total_closed = len(closed_pos)

        return {
            "open_count": len(open_pos),
            "closed_count": total_closed,
            "win_rate": round(len(win_trades) / total_closed, 3) if total_closed > 0 else None,
            "total_realized_pnl": sum(p.realized_pnl or 0 for p in closed_pos),
            "avg_realized_pnl_pct": (
                sum(p.realized_pnl_pct or 0 for p in closed_pos) / total_closed
                if total_closed > 0 else None
            ),
            "instruments": list({p.instrument for p in open_pos}),
        }

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _load(self):
        if self.positions_file.exists():
            try:
                data = json.loads(self.positions_file.read_text(encoding="utf-8"))
                for item in data:
                    pos = Position.model_validate(item)
                    self._positions[pos.position_id] = pos
                logger.info(f"[M5] 加载持仓记录 {len(self._positions)} 条")
            except Exception as e:
                logger.error(f"[M5] 加载持仓文件失败: {e}")

    def _save(self):
        data = [p.model_dump(mode="json") for p in self._positions.values()]
        self.positions_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _get_open(self, position_id: str) -> Position:
        pos = self._positions.get(position_id)
        if pos is None:
            raise KeyError(f"持仓不存在: {position_id}")
        if pos.status == PositionStatus.CLOSED:
            raise ValueError(f"持仓 {position_id} 已关闭，无法操作")
        return pos
