"""
core/market_rules.py — 市场制度规则引擎

集中管理 A 股/港股/期货的交易制度约束：
  - T+1 卖出限制
  - 涨跌停板价格计算
  - 最小交易单位（手数）
  - 交易时段判断

数据源：config/market_config.yaml
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time
from enum import Enum
from typing import Optional

import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class OrderStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class MarketRules:
    """市场制度规则引擎"""

    _LIMIT_PCT = {
        ("A_SHARE", "main"): 0.10,
        ("A_SHARE", "st"): 0.05,
        ("A_SHARE", "gem"): 0.20,
        ("A_SHARE", "star"): 0.20,
        ("A_SHARE", "bse"): 0.30,
        ("HK", "default"): None,
        ("A_FUTURES", "default"): None,
    }

    _MIN_LOT = {
        "A_SHARE": 100,
        "HK": 1,
        "A_FUTURES": 1,
    }

    _SETTLEMENT = {
        "A_SHARE": "T+1",
        "HK": "T+2",
        "A_FUTURES": "T+0",
    }

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self._config = self._load_config(config_path)
        else:
            cp = CONFIG_DIR / "market_config.yaml"
            self._config = self._load_config(str(cp)) if cp.exists() else {}

    @staticmethod
    def _load_config(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # ── T+1 判断 ─────────────────────────────────────────────

    def can_sell(self, market: str, entry_date: date, query_date: Optional[date] = None) -> bool:
        """判断是否可以卖出。

        A 股 T+1：entry_date 的下一个交易日才能卖出。
        港股 T+2：不影响卖出（T+0 交易），但交收延迟。
        期货 T+0：可随时卖出。
        """
        settlement = self._SETTLEMENT.get(market, "T+0")
        if settlement == "T+0":
            return True
        query = query_date or date.today()
        if settlement == "T+1":
            return query > entry_date
        if settlement == "T+2":
            return True
        return True

    # ── 涨跌停 ──────────────────────────────────────────────

    def limit_up_price(self, market: str, prev_close: float, board: str = "main") -> Optional[float]:
        """涨停价。返回 None 表示无涨跌停限制。"""
        pct = self._LIMIT_PCT.get((market, board))
        if pct is None:
            return None
        return round(prev_close * (1 + pct), 2)

    def limit_down_price(self, market: str, prev_close: float, board: str = "main") -> Optional[float]:
        """跌停价。返回 None 表示无涨跌停限制。"""
        pct = self._LIMIT_PCT.get((market, board))
        if pct is None:
            return None
        return round(prev_close * (1 - pct), 2)

    def validate_price_within_limit(
        self, market: str, price: float, prev_close: float, board: str = "main"
    ) -> bool:
        """验证价格是否在涨跌停范围内。"""
        lu = self.limit_up_price(market, prev_close, board)
        ld = self.limit_down_price(market, prev_close, board)
        if lu is not None and price > lu + 0.001:
            return False
        if ld is not None and price < ld - 0.001:
            return False
        return True

    # ── 最小手数 ──────────────────────────────────────────────

    def min_lot_size(self, market: str) -> int:
        """最小交易手数（A股100股，港股1股，期货1手）。"""
        return self._MIN_LOT.get(market, 1)

    def round_quantity(self, market: str, quantity: float) -> float:
        """将数量向下取整到最小手数。"""
        lot = self.min_lot_size(market)
        if lot <= 1:
            return quantity
        return int(quantity / lot) * lot

    # ── 交易时段 ──────────────────────────────────────────────

    def is_trading_hours(self, market: str, dt: Optional[datetime] = None) -> bool:
        """判断当前时间是否在交易时段内。"""
        dt = dt or datetime.now()
        mc = self._config.get("markets", {}).get(market, {})
        th = mc.get("trading_hours", {})
        if not th:
            return True

        t = dt.time()
        try:
            mo = time.fromisoformat(th.get("morning_open", "09:30"))
            mc_ = time.fromisoformat(th.get("morning_close", "11:30"))
            ao = time.fromisoformat(th.get("afternoon_open", "13:00"))
            ac = time.fromisoformat(th.get("afternoon_close", "15:00"))
            return (mo <= t <= mc_) or (ao <= t <= ac)
        except (ValueError, TypeError):
            return True

    # ── 订单校验 ──────────────────────────────────────────────

    def validate_order(
        self,
        market: str,
        direction: str,
        quantity: float,
        price: float,
        prev_close: float,
        entry_date: date,
        board: str = "main",
        query_date: Optional[date] = None,
    ) -> tuple:
        """校验订单是否合规。

        Returns:
            (is_valid, reason)
        """
        if quantity <= 0:
            return False, "quantity must be positive"

        if price <= 0:
            return False, "price must be positive"

        lot = self.min_lot_size(market)
        if lot > 1 and int(quantity) % lot != 0:
            return False, f"quantity {quantity} not multiple of min lot {lot}"

        if not self.validate_price_within_limit(market, price, prev_close, board):
            lu = self.limit_up_price(market, prev_close, board)
            ld = self.limit_down_price(market, prev_close, board)
            return False, f"price {price} outside limit [{ld}, {lu}]"

        if direction in ("SELL", "BEARISH") and not self.can_sell(market, entry_date, query_date):
            return False, f"T+1 restriction: cannot sell on same day for {market}"

        return True, ""

    # ── 期货合约规格 ──────────────────────────────────────────

    _FUTURES_SPECS = {
        "IF": {"multiplier": 300, "margin_pct": 0.12, "exchange": "CFFEX", "price_tick": 0.2, "min_lot": 1},
        "IC": {"multiplier": 200, "margin_pct": 0.12, "exchange": "CFFEX", "price_tick": 0.2, "min_lot": 1},
        "IM": {"multiplier": 200, "margin_pct": 0.12, "exchange": "CFFEX", "price_tick": 0.2, "min_lot": 1},
        "IH": {"multiplier": 300, "margin_pct": 0.12, "exchange": "CFFEX", "price_tick": 0.2, "min_lot": 1},
        "T":  {"multiplier": 10000, "margin_pct": 0.02, "exchange": "CFFEX", "price_tick": 0.005, "min_lot": 1},
        "TF": {"multiplier": 10000, "margin_pct": 0.02, "exchange": "CFFEX", "price_tick": 0.005, "min_lot": 1},
        "au": {"multiplier": 1000, "margin_pct": 0.08, "exchange": "SHFE", "price_tick": 0.02, "min_lot": 1},
        "Cu": {"multiplier": 5, "margin_pct": 0.09, "exchange": "SHFE", "price_tick": 10, "min_lot": 1},
    }

    def futures_contract_spec(self, symbol: str) -> Optional[dict]:
        """获取期货合约规格。symbol 可以是 'IF' 或 'IF2504'。"""
        root = ""
        for ch in symbol:
            if ch.isalpha():
                root += ch
            else:
                break
        return self._FUTURES_SPECS.get(root)

    def futures_margin(self, symbol: str, price: float, quantity: int = 1) -> Optional[float]:
        """计算期货保证金。"""
        spec = self.futures_contract_spec(symbol)
        if not spec:
            return None
        return price * spec["multiplier"] * quantity * spec["margin_pct"]

    def futures_notional(self, symbol: str, price: float, quantity: int = 1) -> Optional[float]:
        """计算期货合约名义价值。"""
        spec = self.futures_contract_spec(symbol)
        if not spec:
            return None
        return price * spec["multiplier"] * quantity


# 全局单例
MARKET_RULES = MarketRules()
