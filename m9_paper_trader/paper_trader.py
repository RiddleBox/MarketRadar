"""
m9_paper_trader/paper_trader.py — 模拟盘核心

职责：
  1. 接收 ActionPlan，开立模拟持仓（PaperPosition）
  2. 定期更新价格，检查止损/止盈触发
  3. 持久化到 data/paper_positions.json
  4. 提供持仓快照供 Evaluator 分析

与 M5（真实持仓）完全分离，互不干扰。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

from core.schemas import ActionPlan, Direction, Market

logger = logging.getLogger(__name__)

PAPER_POS_FILE = Path(__file__).parent.parent / "data" / "paper_positions.json"


# ─────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────

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

        # 动态字段
        self.current_price: float = entry_price
        self.unrealized_pnl_pct: float = 0.0
        self.status: str = "OPEN"          # OPEN / HIT / STOP_LOSS / TAKE_PROFIT / EXPIRED / MANUAL
        self.exit_price: Optional[float] = None
        self.exit_time: Optional[datetime] = None
        self.realized_pnl_pct: Optional[float] = None
        self.price_updates: List[dict] = []
        self.max_adverse_excursion: float = 0.0   # 最大不利偏移（MAE）
        self.max_favorable_excursion: float = 0.0  # 最大有利偏移（MFE）

    def update_price(self, price: float, ts: Optional[datetime] = None):
        """更新当前价，计算浮盈，检查止损/止盈"""
        if self.status != "OPEN":
            return
        ts = ts or datetime.now()
        self.current_price = price

        if self.direction == "BULLISH":
            pnl_pct = (price - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - price) / self.entry_price

        self.unrealized_pnl_pct = pnl_pct
        self.max_favorable_excursion = max(self.max_favorable_excursion, pnl_pct)
        self.max_adverse_excursion = min(self.max_adverse_excursion, pnl_pct)

        self.price_updates.append({"price": price, "ts": ts.isoformat(), "pnl_pct": round(pnl_pct, 6)})

        # 止损检查
        if self.direction == "BULLISH" and price <= self.stop_loss_price:
            self._close("STOP_LOSS", price, ts)
        elif self.direction == "BEARISH" and price >= self.stop_loss_price:
            self._close("STOP_LOSS", price, ts)

        # 止盈检查
        if self.take_profit_price:
            if self.direction == "BULLISH" and price >= self.take_profit_price:
                self._close("TAKE_PROFIT", price, ts)
            elif self.direction == "BEARISH" and price <= self.take_profit_price:
                self._close("TAKE_PROFIT", price, ts)

    def _close(self, reason: str, price: float, ts: datetime):
        self.status = reason
        self.exit_price = price
        self.exit_time = ts
        if self.direction == "BULLISH":
            self.realized_pnl_pct = (price - self.entry_price) / self.entry_price
        else:
            self.realized_pnl_pct = (self.entry_price - price) / self.entry_price
        logger.info(
            f"[M9] 模拟持仓关闭 {self.instrument} | {reason} "
            f"| pnl={self.realized_pnl_pct*100:+.2f}%"
        )

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
            "current_price": self.current_price,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "status": self.status,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "realized_pnl_pct": self.realized_pnl_pct,
            "max_adverse_excursion": self.max_adverse_excursion,
            "max_favorable_excursion": self.max_favorable_excursion,
            "price_updates": self.price_updates[-50:],   # 只保留最近50条，省空间
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
        )
        pp.current_price = d.get("current_price", pp.entry_price)
        pp.unrealized_pnl_pct = d.get("unrealized_pnl_pct", 0)
        pp.status = d.get("status", "OPEN")
        pp.exit_price = d.get("exit_price")
        pp.exit_time = datetime.fromisoformat(d["exit_time"]) if d.get("exit_time") else None
        pp.realized_pnl_pct = d.get("realized_pnl_pct")
        pp.max_adverse_excursion = d.get("max_adverse_excursion", 0)
        pp.max_favorable_excursion = d.get("max_favorable_excursion", 0)
        pp.price_updates = d.get("price_updates", [])
        return pp


# ─────────────────────────────────────────────────────────────
# PaperTrader
# ─────────────────────────────────────────────────────────────

class PaperTrader:
    """
    模拟盘管理器。

    使用方式：
      trader = PaperTrader()
      # 从 ActionPlan 开立模拟仓
      pp = trader.open_from_plan(plan, signals, opportunity)
      # 批量更新价格（每日/每小时调用）
      trader.update_all_prices(price_feed)
      # 查看持仓
      trader.list_open()
    """

    def __init__(self, save_path: Path = PAPER_POS_FILE):
        self._save_path = save_path
        self._save_path.parent.mkdir(parents=True, exist_ok=True)
        self._positions: List[PaperPosition] = []
        self._load()

    # ── 开仓 ──────────────────────────────────────────────────

    def open_from_plan(
        self,
        plan: ActionPlan,
        signal_ids: List[str],
        opportunity_id: str,
        signal_intensity: float = 0.0,
        signal_confidence: float = 0.0,
        signal_type: str = "",
    ) -> List[PaperPosition]:
        """从 ActionPlan 批量开立模拟持仓（每个标的一条）"""
        opened = []
        for inst in plan.instruments:
            sl = plan.stop_loss
            tp = plan.take_profit
            ps = plan.position_sizing

            # 推算入场价（用止损反推，或直接用1.0作为基准价）
            # 实际使用时应传入当前市价；这里用 None 表示待填入
            entry_price = 0.0  # 调用方应在 open_position() 时传入实时价

            pp = PaperPosition(
                plan_id=plan.plan_id,
                opportunity_id=opportunity_id,
                signal_ids=signal_ids,
                instrument=inst,
                market=plan.target_market.value if hasattr(plan.target_market, "value") else str(plan.target_market),
                direction=plan.direction.value if hasattr(plan.direction, "value") else str(plan.direction),
                entry_price=entry_price,
                stop_loss_price=0.0,  # 后续通过 open_position() 填入真实价格
                take_profit_price=None,
                quantity=ps.position_size_pct * 1_000_000 if ps else 10000,
                signal_intensity=signal_intensity,
                signal_confidence=signal_confidence,
                signal_type=signal_type,
                time_horizon=plan.time_horizon.value if hasattr(plan.time_horizon, "value") else "",
            )
            self._positions.append(pp)
            opened.append(pp)
            logger.info(f"[M9] 模拟仓已创建（待填入实时价）: {inst} | {plan.direction}")

        self._save()
        return opened

    def open_position(
        self,
        paper_position_id: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: Optional[float] = None,
    ) -> bool:
        """填入实时价格，正式激活模拟持仓"""
        pp = self._get(paper_position_id)
        if not pp:
            return False
        pp.entry_price = entry_price
        pp.current_price = entry_price
        pp.stop_loss_price = stop_loss_price
        pp.take_profit_price = take_profit_price
        self._save()
        logger.info(f"[M9] 模拟仓激活: {pp.instrument} 入场价={entry_price} 止损={stop_loss_price}")
        return True

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
    ) -> PaperPosition:
        """手动开立模拟持仓（不依赖 ActionPlan）"""
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
        )
        self._positions.append(pp)
        self._save()
        logger.info(f"[M9] 手动模拟仓: {instrument} {direction} @ {entry_price}")
        return pp

    # ── 价格更新 ──────────────────────────────────────────────

    def update_all_prices(self, price_feed) -> dict:
        """批量更新所有 OPEN 持仓的价格

        Args:
            price_feed: PriceFeed 实例

        Returns:
            {"updated": int, "closed": List[str]}
        """
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
                    closed.append(pp.paper_position_id)
            else:
                logger.warning(f"[M9] 无法获取价格: {pp.instrument}")

        if updated > 0:
            self._save()

        return {"updated": updated, "closed": closed}

    def update_price(self, paper_position_id: str, price: float) -> bool:
        """更新单个持仓价格"""
        pp = self._get(paper_position_id)
        if not pp:
            return False
        pp.update_price(price)
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
        pp.close_manual(price)
        self._save()
        return True

    def expire_old(self, max_days: int = 90) -> List[str]:
        """将超过 max_days 且仍 OPEN 的持仓标记为 EXPIRED"""
        now = datetime.now()
        expired = []
        for pp in self._positions:
            if pp.status == "OPEN":
                delta = (now - pp.entry_time).days
                if delta > max_days:
                    pp.expire()
                    expired.append(pp.paper_position_id)
        if expired:
            self._save()
        return expired

    # ── 持久化 ──────────────────────────────────────────────

    def _save(self):
        data = [p.to_dict() for p in self._positions]
        self._save_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
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

    def _get(self, paper_position_id: str) -> Optional[PaperPosition]:
        for p in self._positions:
            if p.paper_position_id == paper_position_id:
                return p
        return None
