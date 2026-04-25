"""
m9_paper_trader/paper_trader.py — 模拟盘核心

职责：
  1. 接收 ActionPlan，开立模拟持仓（PaperPosition）
  2. 定期更新价格，检查止损/止盈触发
  3. 应用手续费/滑点模型
  4. 校验市场制度（T+1/涨跌停/最小手数）
  5. 实时风控（日亏损/最大回撤）
  6. 平仓后触发 M6 复盘
  7. 持久化到 data/paper_positions.json

与 M5（真实持仓）完全分离，互不干扰。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.fee_model import FeeModel, DEFAULT_FEE_MODEL
from core.market_rules import MarketRules, OrderStatus, MARKET_RULES
from core.schemas import ActionPlan, Direction, Market
from m9_paper_trader.price_feed import EquityCurveTracker

logger = logging.getLogger(__name__)

PAPER_POS_FILE = Path(__file__).parent.parent / "data" / "paper_positions.json"
TRADE_LOG_FILE = Path(__file__).parent.parent / "data" / "paper_trade_log.json"


# ─────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────


class PaperOrder:
    """模拟订单"""

    def __init__(
        self,
        instrument: str,
        market: str,
        direction: str,
        quantity: float,
        price: float,
        order_type: str = "MARKET",
        paper_position_id: Optional[str] = None,
        plan_id: str = "",
        opportunity_id: str = "",
    ):
        self.order_id: str = f"ord_{uuid.uuid4().hex[:10]}"
        self.instrument = instrument
        self.market = market
        self.direction = direction
        self.quantity = quantity
        self.price = price
        self.order_type = order_type
        self.paper_position_id = paper_position_id
        self.plan_id = plan_id
        self.opportunity_id = opportunity_id
        self.status: str = OrderStatus.SUBMITTED.value
        self.reject_reason: str = ""
        self.fill_price: Optional[float] = None
        self.fill_time: Optional[datetime] = None
        self.fee_paid: float = 0.0
        self.slippage_paid: float = 0.0
        self.created_at: datetime = datetime.now()

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "instrument": self.instrument,
            "market": self.market,
            "direction": self.direction,
            "quantity": self.quantity,
            "price": self.price,
            "order_type": self.order_type,
            "paper_position_id": self.paper_position_id,
            "plan_id": self.plan_id,
            "opportunity_id": self.opportunity_id,
            "status": self.status,
            "reject_reason": self.reject_reason,
            "fill_price": self.fill_price,
            "fill_time": self.fill_time.isoformat() if self.fill_time else None,
            "fee_paid": self.fee_paid,
            "slippage_paid": self.slippage_paid,
            "created_at": self.created_at.isoformat(),
        }


class PaperPosition:
    """单条模拟持仓"""

    def __init__(
        self,
        plan_id: str,
        opportunity_id: str,
        signal_ids: List[str],
        instrument: str,
        market: str,
        direction: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: Optional[float],
        quantity: float,
        signal_intensity: float = 0.0,
        signal_confidence: float = 0.0,
        signal_type: str = "",
        time_horizon: str = "",
        entry_time: Optional[datetime] = None,
        paper_position_id: Optional[str] = None,
        prev_close: float = 0.0,
        board: str = "main",
    ):
        self.paper_position_id = paper_position_id or f"pp_{uuid.uuid4().hex[:10]}"
        self.plan_id = plan_id
        self.opportunity_id = opportunity_id
        self.signal_ids = signal_ids
        self.instrument = instrument
        self.market = market
        self.direction = direction
        self.entry_price = entry_price
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self.quantity = quantity
        self.signal_intensity = signal_intensity
        self.signal_confidence = signal_confidence
        self.signal_type = signal_type
        self.time_horizon = time_horizon
        self.entry_time = entry_time or datetime.now()
        self.entry_date: date = self.entry_time.date()
        self.prev_close = prev_close
        self.board = board

        self.current_price: float = entry_price
        self.unrealized_pnl_pct: float = 0.0
        self.realized_pnl_pct: Optional[float] = None
        self.realized_pnl_after_fees: Optional[float] = None
        self.status: str = "OPEN"
        self.exit_price: Optional[float] = None
        self.exit_time: Optional[datetime] = None
        self.price_updates: List[dict] = []
        self.max_adverse_excursion: float = 0.0
        self.max_favorable_excursion: float = 0.0
        self.fee_paid: float = 0.0
        self.orders: List[PaperOrder] = []

    def update_price(self, price: float, ts: Optional[datetime] = None):
        """更新当前价，计算浮盈，检查止损/止盈"""
        if self.status != "OPEN":
            return
        ts = ts or datetime.now()
        self.current_price = price

        if self.direction == "BULLISH":
            pnl_pct = (
                (price - self.entry_price) / self.entry_price
                if self.entry_price > 0
                else 0
            )
        else:
            pnl_pct = (
                (self.entry_price - price) / self.entry_price
                if self.entry_price > 0
                else 0
            )

        self.unrealized_pnl_pct = pnl_pct
        self.max_favorable_excursion = max(self.max_favorable_excursion, pnl_pct)
        self.max_adverse_excursion = min(self.max_adverse_excursion, pnl_pct)

        self.price_updates.append(
            {"price": price, "ts": ts.isoformat(), "pnl_pct": round(pnl_pct, 6)}
        )

        if self.direction == "BULLISH" and price <= self.stop_loss_price:
            self._close("STOP_LOSS", price, ts)
        elif self.direction == "BEARISH" and price >= self.stop_loss_price:
            self._close("STOP_LOSS", price, ts)

        if self.status == "OPEN" and self.take_profit_price:
            if self.direction == "BULLISH" and price >= self.take_profit_price:
                self._close("TAKE_PROFIT", price, ts)
            elif self.direction == "BEARISH" and price <= self.take_profit_price:
                self._close("TAKE_PROFIT", price, ts)

    def _close(self, reason: str, price: float, ts: datetime):
        self.status = reason
        self.exit_price = price
        self.exit_time = ts
        if self.direction == "BULLISH":
            self.realized_pnl_pct = (
                (price - self.entry_price) / self.entry_price
                if self.entry_price > 0
                else 0
            )
        else:
            self.realized_pnl_pct = (
                (self.entry_price - price) / self.entry_price
                if self.entry_price > 0
                else 0
            )
        logger.info(
            f"[M9] 模拟持仓关闭 {self.instrument} | {reason} "
            f"| pnl={self.realized_pnl_pct * 100:+.2f}%"
        )

    def apply_fees(self, fee_model: FeeModel):
        """在平仓时计算并扣除手续费/滑点。"""
        if self.realized_pnl_pct is None or self.entry_price <= 0:
            return
        notional = self.entry_price * self.quantity
        exit_notional = (self.exit_price or self.current_price) * self.quantity
        direction = self.direction
        buy_notional = notional if direction == "BULLISH" else exit_notional
        sell_notional = exit_notional if direction == "BULLISH" else notional
        total_cost = fee_model.round_trip_cost(buy_notional, sell_notional)
        self.fee_paid = total_cost
        gross_pnl = notional * self.realized_pnl_pct
        net_pnl = gross_pnl - total_cost
        self.realized_pnl_after_fees = net_pnl / notional if notional > 0 else 0

    def close_manual(self, price: float):
        self._close("MANUAL", price, datetime.now())

    def expire(self):
        self._close("EXPIRED", self.current_price, datetime.now())

    def to_dict(self) -> dict:
        return {
            "paper_position_id": self.paper_position_id,
            "plan_id": self.plan_id,
            "opportunity_id": self.opportunity_id,
            "signal_ids": self.signal_ids,
            "instrument": self.instrument,
            "market": self.market,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "quantity": self.quantity,
            "signal_intensity": self.signal_intensity,
            "signal_confidence": self.signal_confidence,
            "signal_type": self.signal_type,
            "time_horizon": self.time_horizon,
            "entry_time": self.entry_time.isoformat(),
            "entry_date": self.entry_date.isoformat(),
            "prev_close": self.prev_close,
            "board": self.board,
            "current_price": self.current_price,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "status": self.status,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "realized_pnl_pct": self.realized_pnl_pct,
            "realized_pnl_after_fees": self.realized_pnl_after_fees,
            "max_adverse_excursion": self.max_adverse_excursion,
            "max_favorable_excursion": self.max_favorable_excursion,
            "fee_paid": self.fee_paid,
            "price_updates": self.price_updates[-50:],
            "orders": [o.to_dict() for o in self.orders],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PaperPosition":
        pp = cls(
            plan_id=d["plan_id"],
            opportunity_id=d["opportunity_id"],
            signal_ids=d.get("signal_ids", []),
            instrument=d["instrument"],
            market=d["market"],
            direction=d["direction"],
            entry_price=d["entry_price"],
            stop_loss_price=d["stop_loss_price"],
            take_profit_price=d.get("take_profit_price"),
            quantity=d.get("quantity", 0),
            signal_intensity=d.get("signal_intensity", 0),
            signal_confidence=d.get("signal_confidence", 0),
            signal_type=d.get("signal_type", ""),
            time_horizon=d.get("time_horizon", ""),
            entry_time=datetime.fromisoformat(d["entry_time"]),
            paper_position_id=d.get("paper_position_id"),
            prev_close=d.get("prev_close", 0),
            board=d.get("board", "main"),
        )
        pp.entry_date = (
            date.fromisoformat(d["entry_date"])
            if d.get("entry_date")
            else pp.entry_time.date()
        )
        pp.current_price = d.get("current_price", pp.entry_price)
        pp.unrealized_pnl_pct = d.get("unrealized_pnl_pct", 0)
        pp.status = d.get("status", "OPEN")
        pp.exit_price = d.get("exit_price")
        pp.exit_time = (
            datetime.fromisoformat(d["exit_time"]) if d.get("exit_time") else None
        )
        pp.realized_pnl_pct = d.get("realized_pnl_pct")
        pp.realized_pnl_after_fees = d.get("realized_pnl_after_fees")
        pp.max_adverse_excursion = d.get("max_adverse_excursion", 0)
        pp.max_favorable_excursion = d.get("max_favorable_excursion", 0)
        pp.fee_paid = d.get("fee_paid", 0)
        pp.price_updates = d.get("price_updates", [])
        return pp


# ─────────────────────────────────────────────────────────────
# RiskMonitor
# ─────────────────────────────────────────────────────────────


class RiskMonitor:
    """实时风控监控器（含组合级风控）"""

    def __init__(
        self,
        initial_capital: float = 1_000_000,
        max_daily_drawdown_pct: float = 0.05,
        max_total_drawdown_pct: float = 0.10,
        max_single_position_pct: float = 0.08,
        max_total_exposure_pct: float = 0.30,
        max_theme_exposure_pct: float = 0.15,
        high_corr_threshold: float = 0.85,
    ):
        self.initial_capital = initial_capital
        self.max_daily_drawdown_pct = max_daily_drawdown_pct
        self.max_total_drawdown_pct = max_total_drawdown_pct
        self.max_single_position_pct = max_single_position_pct
        self.max_total_exposure_pct = max_total_exposure_pct
        self.max_theme_exposure_pct = max_theme_exposure_pct
        self.high_corr_threshold = high_corr_threshold
        self._daily_start_equity: Optional[float] = None
        self._peak_equity: float = initial_capital
        self._trading_halted: bool = False

    def reset_daily(self, current_equity: float):
        self._daily_start_equity = current_equity
        self._peak_equity = max(self._peak_equity, current_equity)
        self._trading_halted = False

    def check_before_open(
        self, position_notional: float, current_equity: float
    ) -> tuple:
        """开仓前风控检查。

        Returns:
            (allowed, reason)
        """
        if self._trading_halted:
            return False, "trading halted due to risk limit breach"

        if current_equity <= 0:
            return False, "equity is zero or negative"

        single_pct = position_notional / self.initial_capital
        if single_pct > self.max_single_position_pct:
            return (
                False,
                f"single position {single_pct:.1%} exceeds limit {self.max_single_position_pct:.1%}",
            )

        total_dd = (
            (self._peak_equity - current_equity) / self._peak_equity
            if self._peak_equity > 0
            else 0
        )
        if total_dd >= self.max_total_drawdown_pct:
            self._trading_halted = True
            return (
                False,
                f"total drawdown {total_dd:.1%} >= limit {self.max_total_drawdown_pct:.1%}",
            )

        if self._daily_start_equity and self._daily_start_equity > 0:
            daily_dd = (
                self._daily_start_equity - current_equity
            ) / self._daily_start_equity
            if daily_dd >= self.max_daily_drawdown_pct:
                self._trading_halted = True
                return (
                    False,
                    f"daily drawdown {daily_dd:.1%} >= limit {self.max_daily_drawdown_pct:.1%}",
                )

        return True, ""

    def on_position_closed(self, position: PaperPosition, fee_model: FeeModel):
        """平仓后检查风控状态。"""
        position.apply_fees(fee_model)

    def check_portfolio_risk(
        self,
        positions: List["PaperPosition"],
        new_position: Optional["PaperPosition"] = None,
        theme_map: Optional[Dict[str, str]] = None,
        corr_matrix: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> List[str]:
        """组合级风控检查。

        Args:
            positions: 当前持仓列表
            new_position: 拟新增仓位（None 时仅检查存量）
            theme_map: 标的→主题映射，如 {"510300.SH": "大盘蓝筹", "588000.SH": "科技"}
            corr_matrix: 标的→标的→相关系数，如 {"510300.SH": {"588000.SH": 0.72}}

        Returns:
            风控警告列表（空列表表示无风险）
        """
        warnings = []

        all_positions = list(positions)
        if new_position:
            all_positions.append(new_position)

        total_notional = sum(
            p.current_price * p.quantity
            for p in all_positions
            if p.status == "OPEN" and p.entry_price > 0
        )
        total_pct = (
            total_notional / self.initial_capital if self.initial_capital > 0 else 0
        )

        if total_pct > self.max_total_exposure_pct:
            warnings.append(
                f"总仓位 {total_pct:.1%} 超过限制 {self.max_total_exposure_pct:.1%}"
            )

        if theme_map:
            theme_notional: Dict[str, float] = {}
            for p in all_positions:
                if p.status != "OPEN" or p.entry_price <= 0:
                    continue
                instrument = p.instrument or ""
                theme = theme_map.get(instrument, "未分类")
                theme_notional[theme] = (
                    theme_notional.get(theme, 0) + p.current_price * p.quantity
                )

            for theme, notional in theme_notional.items():
                theme_pct = (
                    notional / self.initial_capital if self.initial_capital > 0 else 0
                )
                if theme_pct > self.max_theme_exposure_pct:
                    warnings.append(
                        f"主题'{theme}'暴露 {theme_pct:.1%} 超过限制 {self.max_theme_exposure_pct:.1%}"
                    )

        if corr_matrix and new_position:
            new_inst = new_position.instrument or ""
            for p in positions:
                if p.status != "OPEN" or p.entry_price <= 0:
                    continue
                existing_inst = p.instrument or ""
                if new_inst in corr_matrix and existing_inst in corr_matrix.get(
                    new_inst, {}
                ):
                    corr = corr_matrix[new_inst].get(existing_inst, 0)
                    if abs(corr) >= self.high_corr_threshold:
                        same_dir = (
                            (new_position.direction == p.direction)
                            if hasattr(new_position, "direction")
                            and hasattr(p, "direction")
                            else True
                        )
                        if same_dir:
                            warnings.append(
                                f"新仓 {new_inst} 与已有 {existing_inst} 高相关({corr:.2f})同方向，风险集中"
                            )

        return warnings

    def compute_equity(self, positions: List[PaperPosition], cash: float) -> float:
        """计算总权益 = 现金 + 所有未平仓浮盈。"""
        unrealized = 0.0
        for p in positions:
            if p.status == "OPEN" and p.entry_price > 0:
                if p.direction == "BULLISH":
                    unrealized += (p.current_price - p.entry_price) * p.quantity
                else:
                    unrealized += (p.entry_price - p.current_price) * p.quantity
        return cash + unrealized

    @property
    def is_halted(self) -> bool:
        return self._trading_halted


# ─────────────────────────────────────────────────────────────
# PaperTrader
# ─────────────────────────────────────────────────────────────


class PaperTrader:
    """
    模拟盘管理器。
    """

    def __init__(
        self,
        save_path: Path = PAPER_POS_FILE,
        fee_model: Optional[FeeModel] = None,
        market_rules: Optional[MarketRules] = None,
        risk_monitor: Optional[RiskMonitor] = None,
        on_position_closed: Optional[Callable] = None,
        initial_capital: float = 1_000_000,
    ):
        self._save_path = save_path
        self._save_path.parent.mkdir(parents=True, exist_ok=True)
        self._positions: List[PaperPosition] = []
        self._trade_log: List[dict] = []
        self._fee_model = fee_model or DEFAULT_FEE_MODEL
        self._market_rules = market_rules or MARKET_RULES
        self._risk_monitor = risk_monitor or RiskMonitor(
            initial_capital=initial_capital
        )
        self._on_position_closed = on_position_closed
        self._initial_capital = initial_capital
        self._cash = initial_capital
        self._closed_today = 0
        self._daily_pnl = 0.0
        self._equity_tracker = EquityCurveTracker()
        self._load()

    # ── 开仓 ──────────────────────────────────────────────────

    def open_from_plan(
        self,
        plan: ActionPlan,
        signal_ids: List[str],
        opportunity_id: str,
        entry_price: float,
        prev_close: float = 0.0,
        signal_intensity: float = 0.0,
        signal_confidence: float = 0.0,
        signal_type: str = "",
    ) -> List[PaperPosition]:
        """从 ActionPlan 批量开立模拟持仓"""
        opened = []
        for inst in plan.primary_instruments:
            sl = plan.stop_loss
            tp = plan.take_profit
            ps = plan.position_sizing
            market = (
                plan.market.value if hasattr(plan.market, "value") else str(plan.market)
            )
            direction = (
                plan.direction.value
                if hasattr(plan.direction, "value")
                else str(plan.direction)
            )

            if entry_price <= 0:
                logger.warning(
                    f"[M9] open_from_plan: entry_price <= 0 for {inst}, skipping"
                )
                continue

            board = self._infer_board(inst, market)
            quantity = self._compute_quantity(plan, entry_price, market)

            is_valid, reason = self._market_rules.validate_order(
                market=market,
                direction="BUY" if direction == "BULLISH" else "SELL",
                quantity=quantity,
                price=entry_price,
                prev_close=prev_close or entry_price,
                entry_date=date.today(),
                board=board,
            )
            if not is_valid:
                logger.warning(f"[M9] 订单校验失败 {inst}: {reason}")
                continue

            notional = entry_price * quantity
            equity = self._risk_monitor.compute_equity(
                self._positions, self._initial_capital_estimate()
            )
            allowed, risk_reason = self._risk_monitor.check_before_open(
                notional, equity
            )
            if not allowed:
                logger.warning(f"[M9] 风控拒绝开仓 {inst}: {risk_reason}")
                continue

            sl_price = (
                entry_price * (1 - sl.stop_loss_value / 100)
                if direction == "BULLISH"
                else entry_price * (1 + sl.stop_loss_value / 100)
            )
            tp_price = None
            if tp.take_profit_value > 0:
                tp_price = (
                    entry_price * (1 + tp.take_profit_value / 100)
                    if direction == "BULLISH"
                    else entry_price * (1 - tp.take_profit_value / 100)
                )

            pp = PaperPosition(
                plan_id=plan.plan_id,
                opportunity_id=opportunity_id,
                signal_ids=signal_ids,
                instrument=inst,
                market=market,
                direction=direction,
                entry_price=entry_price,
                stop_loss_price=sl_price,
                take_profit_price=tp_price,
                quantity=quantity,
                signal_intensity=signal_intensity,
                signal_confidence=signal_confidence,
                signal_type=signal_type,
                time_horizon="",
                prev_close=prev_close or entry_price,
                board=board,
            )

            order = PaperOrder(
                instrument=inst,
                market=market,
                direction="BUY" if direction == "BULLISH" else "SELL",
                quantity=quantity,
                price=entry_price,
                paper_position_id=pp.paper_position_id,
                plan_id=plan.plan_id,
                opportunity_id=opportunity_id,
            )
            order.status = OrderStatus.FILLED.value
            order.fill_price = entry_price
            order.fill_time = datetime.now()
            order.fee_paid = self._fee_model.buy_cost(entry_price * quantity)
            pp.orders.append(order)
            pp.fee_paid = order.fee_paid

            self._positions.append(pp)
            self._log_trade("OPEN", pp, order)
            opened.append(pp)
            logger.info(f"[M9] 模拟仓已创建: {inst} | {direction} @ {entry_price}")

        self._save()
        return opened

    def open_manual(
        self,
        instrument: str,
        market: str,
        direction: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: Optional[float] = None,
        quantity: float = 10000,
        signal_ids: Optional[List[str]] = None,
        signal_intensity: float = 0.0,
        signal_confidence: float = 0.0,
        signal_type: str = "",
        opportunity_id: str = "",
        prev_close: float = 0.0,
        board: str = "main",
    ) -> Optional[PaperPosition]:
        """手动开立模拟持仓（不依赖 ActionPlan）"""
        if entry_price <= 0:
            logger.warning("[M9] open_manual: entry_price <= 0")
            return None

        is_valid, reason = self._market_rules.validate_order(
            market=market,
            direction="BUY" if direction == "BULLISH" else "SELL",
            quantity=quantity,
            price=entry_price,
            prev_close=prev_close or entry_price,
            entry_date=date.today(),
            board=board,
        )
        if not is_valid:
            logger.warning(f"[M9] 手动开仓校验失败: {reason}")
            return None

        notional = entry_price * quantity
        equity = self._risk_monitor.compute_equity(
            self._positions, self._initial_capital_estimate()
        )
        allowed, risk_reason = self._risk_monitor.check_before_open(notional, equity)
        if not allowed:
            logger.warning(f"[M9] 风控拒绝手动开仓: {risk_reason}")
            return None

        pp = PaperPosition(
            plan_id=f"manual_{uuid.uuid4().hex[:8]}",
            opportunity_id=opportunity_id,
            signal_ids=signal_ids or [],
            instrument=instrument,
            market=market,
            direction=direction,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            quantity=quantity,
            signal_intensity=signal_intensity,
            signal_confidence=signal_confidence,
            signal_type=signal_type,
            prev_close=prev_close or entry_price,
            board=board,
        )

        order = PaperOrder(
            instrument=instrument,
            market=market,
            direction="BUY" if direction == "BULLISH" else "SELL",
            quantity=quantity,
            price=entry_price,
            paper_position_id=pp.paper_position_id,
        )
        order.status = OrderStatus.FILLED.value
        order.fill_price = entry_price
        order.fill_time = datetime.now()
        order.fee_paid = self._fee_model.buy_cost(entry_price * quantity)
        pp.orders.append(order)
        pp.fee_paid = order.fee_paid

        self._positions.append(pp)
        self._log_trade("OPEN", pp, order)
        self._save()
        logger.info(f"[M9] 手动模拟仓: {instrument} {direction} @ {entry_price}")
        return pp

    # ── 价格更新 ──────────────────────────────────────────────

    def update_all_prices(self, price_feed) -> dict:
        """批量更新所有 OPEN 持仓的价格"""
        open_positions = [p for p in self._positions if p.status == "OPEN"]
        updated = 0
        closed = []

        for pp in open_positions:
            snapshot = price_feed.get_price(pp.instrument)
            if snapshot and snapshot.price > 0:
                was_open = pp.status == "OPEN"
                pp.update_price(snapshot.price, snapshot.timestamp)
                updated += 1
                if pp.status != "OPEN" and was_open:
                    self._on_close(pp)
                    closed.append(pp.paper_position_id)
            else:
                logger.warning(f"[M9] 无法获取价格: {pp.instrument}")

        if updated > 0:
            self._save()

        return {"updated": updated, "closed": closed}

    def update_price(self, paper_position_id: str, price: float) -> bool:
        pp = self._get(paper_position_id)
        if not pp:
            return False
        was_open = pp.status == "OPEN"
        pp.update_price(price)
        if pp.status != "OPEN" and was_open:
            self._on_close(pp)
        self._save()
        return True

    # ── 查询 ──────────────────────────────────────────────────

    def list_open(self) -> List[PaperPosition]:
        return [p for p in self._positions if p.status == "OPEN"]

    def list_closed(self) -> List[PaperPosition]:
        return [p for p in self._positions if p.status != "OPEN"]

    def list_all(self) -> List[PaperPosition]:
        return list(self._positions)

    def get(self, paper_position_id: str) -> Optional[PaperPosition]:
        return self._get(paper_position_id)

    # ── 手动平仓 ──────────────────────────────────────────────

    def close_manual(self, paper_position_id: str, price: float) -> bool:
        pp = self._get(paper_position_id)
        if not pp:
            return False
        was_open = pp.status == "OPEN"
        pp.close_manual(price)
        if was_open:
            self._on_close(pp)
        self._save()
        return True

    def expire_old(self, max_days: int = 90) -> List[str]:
        now = datetime.now()
        expired = []
        for pp in self._positions:
            if pp.status == "OPEN":
                delta = (now - pp.entry_time).days
                if delta > max_days:
                    pp.expire()
                    self._on_close(pp)
                    expired.append(pp.paper_position_id)
        if expired:
            self._save()
        return expired

    # ── 内部方法 ──────────────────────────────────────────────

    def _on_close(self, pp: PaperPosition):
        """平仓后处理：扣费 + 记录 + 风控 + 回调。"""
        pp.apply_fees(self._fee_model)
        self._risk_monitor.on_position_closed(pp, self._fee_model)
        self._closed_today += 1
        if pp.realized_pnl_pct is not None and pp.entry_price > 0:
            notional = pp.entry_price * pp.quantity
            self._daily_pnl += notional * pp.realized_pnl_pct - pp.fee_paid
        self._log_trade("CLOSE", pp)

        if self._on_position_closed:
            try:
                self._on_position_closed(pp)
            except Exception as e:
                logger.error(f"[M9] on_position_closed callback error: {e}")

    # ── 资金曲线 ──────────────────────────────────────────────

    def record_equity(self, dt: Optional[date] = None):
        """记录当日权益到资金曲线。"""
        dt = dt or date.today()
        equity = self._risk_monitor.compute_equity(self._positions, self._cash)
        unrealized = equity - self._cash
        self._equity_tracker.record(
            dt=dt,
            equity=equity,
            cash=self._cash,
            unrealized_pnl=unrealized,
            open_count=len(self.list_open()),
            closed_today=self._closed_today,
            daily_pnl=self._daily_pnl,
        )

    def get_equity_curve(self, start_date: Optional[date] = None) -> List[dict]:
        return self._equity_tracker.get_curve(start_date)

    def reset_daily_counters(self):
        """每日开盘前调用，重置日统计。"""
        self._closed_today = 0
        self._daily_pnl = 0.0
        equity = self._risk_monitor.compute_equity(self._positions, self._cash)
        self._risk_monitor.reset_daily(equity)

    # ── 期货支持 ──────────────────────────────────────────────

    def open_futures(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: int = 1,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        signal_ids: Optional[List[str]] = None,
        opportunity_id: str = "",
    ) -> Optional[PaperPosition]:
        """开立期货模拟持仓。自动计算保证金和合约乘数。"""
        spec = self._market_rules.futures_contract_spec(symbol)
        if not spec:
            logger.warning(f"[M9] unknown futures symbol: {symbol}")
            return None

        margin = self._market_rules.futures_margin(symbol, entry_price, quantity) or 0
        notional = (
            self._market_rules.futures_notional(symbol, entry_price, quantity) or 0
        )
        equity = self._risk_monitor.compute_equity(self._positions, self._cash)
        allowed, risk_reason = self._risk_monitor.check_before_open(margin, equity)
        if not allowed:
            logger.warning(f"[M9] futures risk rejected {symbol}: {risk_reason}")
            return None

        pp = PaperPosition(
            plan_id=f"fut_{uuid.uuid4().hex[:8]}",
            opportunity_id=opportunity_id,
            signal_ids=signal_ids or [],
            instrument=symbol,
            market="A_FUTURES",
            direction=direction,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price or entry_price * 0.97,
            take_profit_price=take_profit_price,
            quantity=quantity,
            prev_close=entry_price,
            board="default",
        )

        order = PaperOrder(
            instrument=symbol,
            market="A_FUTURES",
            direction="BUY" if direction == "BULLISH" else "SELL",
            quantity=quantity,
            price=entry_price,
            paper_position_id=pp.paper_position_id,
        )
        order.status = OrderStatus.FILLED.value
        order.fill_price = entry_price
        order.fill_time = datetime.now()
        order.fee_paid = self._fee_model.buy_cost(margin)
        pp.orders.append(order)
        pp.fee_paid = order.fee_paid

        self._positions.append(pp)
        self._cash -= margin + order.fee_paid
        self._log_trade("OPEN_FUTURES", pp, order)
        self._save()
        logger.info(
            f"[M9] futures position: {symbol} {direction} @ {entry_price} x{quantity} margin={margin:.0f}"
        )
        return pp

    def _compute_quantity(
        self, plan: ActionPlan, entry_price: float, market: str
    ) -> float:
        ps = plan.position_sizing
        if ps and ps.suggested_allocation_pct and entry_price > 0:
            notional = ps.suggested_allocation_pct * self._initial_capital
            raw_qty = notional / entry_price
            return self._market_rules.round_quantity(market, raw_qty)
        return self._market_rules.round_quantity(
            market, 10000 / entry_price if entry_price > 0 else 0
        )

    def _infer_board(self, instrument: str, market: str) -> str:
        code = instrument.split(".")[0]
        if market == "A_SHARE":
            if code.startswith("3"):
                return "gem"
            if code.startswith("68"):
                return "star"
            if code.startswith("8") or code.startswith("4"):
                return "bse"
            return "main"
        return "default"

    def _initial_capital_estimate(self) -> float:
        return self._cash

    def _log_trade(
        self, event: str, pp: PaperPosition, order: Optional[PaperOrder] = None
    ):
        entry = {
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "paper_position_id": pp.paper_position_id,
            "instrument": pp.instrument,
            "market": pp.market,
            "direction": pp.direction,
            "status": pp.status,
            "realized_pnl_pct": pp.realized_pnl_pct,
            "realized_pnl_after_fees": pp.realized_pnl_after_fees,
            "fee_paid": pp.fee_paid,
        }
        if order:
            entry["order_id"] = order.order_id
            entry["order_fee"] = order.fee_paid
        self._trade_log.append(entry)

    def _save(self):
        data = [p.to_dict() for p in self._positions]
        self._save_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        if self._trade_log:
            TRADE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            TRADE_LOG_FILE.write_text(
                json.dumps(
                    self._trade_log[-500:], ensure_ascii=False, indent=2, default=str
                ),
                encoding="utf-8",
            )

    def _load(self):
        if self._save_path.exists():
            try:
                data = json.loads(self._save_path.read_text(encoding="utf-8"))
                self._positions = [PaperPosition.from_dict(d) for d in data]
                logger.info(f"[M9] 加载 {len(self._positions)} 条模拟持仓")
            except Exception as e:
                logger.error(f"[M9] 加载失败: {e}")
                self._positions = []
        else:
            self._positions = []
        if TRADE_LOG_FILE.exists():
            try:
                self._trade_log = json.loads(TRADE_LOG_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._trade_log = []

    def _get(self, paper_position_id: str) -> Optional[PaperPosition]:
        for p in self._positions:
            if p.paper_position_id == paper_position_id:
                return p
        return None
