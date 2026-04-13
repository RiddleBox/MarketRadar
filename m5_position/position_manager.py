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
    ActionType,
    Direction,
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

    def open_position(self, plan: ActionPlan, entry_price: float) -> Position:
        """开仓：基于 ActionPlan 建立新持仓

        Args:
            plan: M4 输出的行动计划
            entry_price: 实际入场价格

        Returns:
            新建的 Position 对象
        """
        if plan.action_type == ActionType.WATCH:
            raise ValueError("WATCH 类型的行动计划不建立实际持仓")

        now = datetime.now()

        # 计算止损价（如果计划中有具体止损价格）
        stop_price = plan.stop_loss.stop_price

        position = Position(
            position_id=f"pos_{uuid.uuid4().hex[:8]}",
            plan_id=plan.plan_id,
            opportunity_id=plan.opportunity_id,
            status=PositionStatus.ACTIVE,
            instrument=plan.instrument,
            direction=plan.direction,
            entry_price=entry_price,
            entry_time=now,
            size=plan.position_sizing.value,
            current_price=entry_price,
            unrealized_pnl=0.0,
            stop_loss_price=stop_price,
            take_profit_price=None,  # 由 ActionPlan.take_profit 决定，后续可更新
            updates=[
                PositionUpdate(
                    update_time=now,
                    update_type="OPEN",
                    description=f"开仓 | 入场价={entry_price} | 止损={stop_price or '条件触发'}",
                    price=entry_price,
                )
            ],
            close_reason=None,
            realized_pnl=None,
        )

        self._positions[position.position_id] = position
        self._save()

        logger.info(
            f"[M5] 开仓 | id={position.position_id} instrument={plan.instrument} "
            f"direction={plan.direction.value} entry={entry_price} stop={stop_price}"
        )
        return position

    def update_price(self, position_id: str, current_price: float) -> Optional[PositionUpdate]:
        """更新当前价格，重新计算浮盈

        Returns:
            PositionUpdate 记录（如有状态变化），否则 None
        """
        pos = self._get_active(position_id)
        old_price = pos.current_price
        pos.current_price = current_price

        # 计算浮盈
        if pos.direction == Direction.BULLISH:
            pos.unrealized_pnl = (current_price - pos.entry_price) / pos.entry_price
        else:  # BEARISH / SHORT
            pos.unrealized_pnl = (pos.entry_price - current_price) / pos.entry_price

        update = PositionUpdate(
            update_time=datetime.now(),
            update_type="PRICE_UPDATE",
            description=f"价格更新 {old_price:.4f} → {current_price:.4f} | 浮盈={pos.unrealized_pnl*100:.2f}%",
            price=current_price,
        )
        pos.updates.append(update)
        self._save()

        return update

    def check_triggers(self, position_id: str) -> Optional[str]:
        """检查止损/止盈是否触发

        Returns:
            触发信息字符串（如："【止损触发】价格 9.85 已低于止损价 10.00，请立即执行平仓。"）
            None 表示未触发
        """
        pos = self._get_active(position_id)
        price = pos.current_price

        if price is None:
            return None

        # 止损检查
        if pos.stop_loss_price is not None:
            if pos.direction == Direction.BULLISH and price <= pos.stop_loss_price:
                return (
                    f"【止损触发】{pos.instrument} 当前价 {price:.4f} ≤ 止损价 {pos.stop_loss_price:.4f}，"
                    f"浮亏 {abs(pos.unrealized_pnl)*100:.2f}%，请立即执行平仓。"
                )
            elif pos.direction in (Direction.BEARISH, Direction.NEUTRAL) and price >= pos.stop_loss_price:
                return (
                    f"【止损触发】{pos.instrument} 当前价 {price:.4f} ≥ 止损价 {pos.stop_loss_price:.4f}，"
                    f"浮亏 {abs(pos.unrealized_pnl)*100:.2f}%，请立即执行平仓。"
                )

        # 止盈检查
        if pos.take_profit_price is not None:
            if pos.direction == Direction.BULLISH and price >= pos.take_profit_price:
                return (
                    f"【止盈触发】{pos.instrument} 当前价 {price:.4f} ≥ 止盈价 {pos.take_profit_price:.4f}，"
                    f"浮盈 {pos.unrealized_pnl*100:.2f}%，建议执行止盈。"
                )
            elif pos.direction in (Direction.BEARISH, Direction.NEUTRAL) and price <= pos.take_profit_price:
                return (
                    f"【止盈触发】{pos.instrument} 当前价 {price:.4f} ≤ 止盈价 {pos.take_profit_price:.4f}，"
                    f"浮盈 {pos.unrealized_pnl*100:.2f}%，建议执行止盈。"
                )

        return None

    def close_position(self, position_id: str, exit_price: float, reason: str) -> Position:
        """平仓

        Args:
            position_id: 持仓 ID
            exit_price: 实际平仓价格
            reason: 平仓原因（"止损" / "止盈" / "手动平仓" / "计划到期" 等）

        Returns:
            已关闭的 Position 对象
        """
        pos = self._get_active(position_id)
        now = datetime.now()

        # 计算实现盈亏
        if pos.direction == Direction.BULLISH:
            realized_pnl = (exit_price - pos.entry_price) / pos.entry_price
        else:
            realized_pnl = (pos.entry_price - exit_price) / pos.entry_price

        pos.status = PositionStatus.CLOSED
        pos.current_price = exit_price
        pos.realized_pnl = realized_pnl
        pos.close_reason = reason
        pos.updates.append(
            PositionUpdate(
                update_time=now,
                update_type="CLOSE",
                description=f"平仓 | 原因={reason} | 平仓价={exit_price:.4f} | 实现盈亏={realized_pnl*100:.2f}%",
                price=exit_price,
            )
        )

        self._save()

        result_emoji = "✅" if realized_pnl >= 0 else "❌"
        logger.info(
            f"[M5] 平仓 {result_emoji} | id={position_id} instrument={pos.instrument} "
            f"原因={reason} 盈亏={realized_pnl*100:.2f}%"
        )
        return pos

    def update_stop_loss(self, position_id: str, new_stop: float, reason: str) -> Position:
        """更新止损价（移动止盈/止损）"""
        pos = self._get_active(position_id)
        old_stop = pos.stop_loss_price
        pos.stop_loss_price = new_stop
        pos.updates.append(
            PositionUpdate(
                update_time=datetime.now(),
                update_type="STOP_LOSS_UPDATE",
                description=f"止损更新 {old_stop} → {new_stop} | 原因: {reason}",
                price=pos.current_price,
            )
        )
        self._save()
        logger.info(f"[M5] 止损更新 | id={position_id} {old_stop} → {new_stop}")
        return pos

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_position(self, position_id: str) -> Optional[Position]:
        return self._positions.get(position_id)

    def get_all_positions(self) -> List[Position]:
        return list(self._positions.values())

    def get_active_positions(self) -> List[Position]:
        return [p for p in self._positions.values() if p.status == PositionStatus.ACTIVE]

    def get_summary(self) -> dict:
        """持仓摘要统计"""
        active = self.get_active_positions()
        closed = [p for p in self._positions.values() if p.status == PositionStatus.CLOSED]

        win_trades = [p for p in closed if p.realized_pnl and p.realized_pnl > 0]
        total_closed = len(closed)

        return {
            "active_count": len(active),
            "closed_count": total_closed,
            "win_rate": len(win_trades) / total_closed if total_closed > 0 else None,
            "total_unrealized_pnl": sum(p.unrealized_pnl or 0 for p in active),
            "total_realized_pnl": sum(p.realized_pnl or 0 for p in closed),
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

    def _get_active(self, position_id: str) -> Position:
        pos = self._positions.get(position_id)
        if pos is None:
            raise KeyError(f"持仓不存在: {position_id}")
        if pos.status == PositionStatus.CLOSED:
            raise ValueError(f"持仓 {position_id} 已关闭，无法操作")
        return pos
