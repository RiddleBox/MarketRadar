"""
m12_opportunity_catcher/market_strategies.py — 市场差异化异动策略配置

设计原则（见 PRINCIPLES.md）：
  5. 市场规则不可违反 — T+1/涨跌停/最小手数由 core/market_rules 管理
  不同市场的扫描频率、数据源、止损策略、入场时机均不同。

A股：盘后扫描+盘中快速，T+1更紧止损，涨停观察池
港股：盘中扫描，T+0立即入场
美股：盘中扫描（北京夜间），T+0立即入场
"""
from __future__ import annotations

from core.schemas import Market, StopLossConfig


class MarketAnomalyStrategy:
    """市场差异化异动策略"""

    def __init__(
        self,
        market: Market,
        scan_mode: str = "daily",
        scan_times: list = None,
        price_feed: str = "baostock",
        min_atr_multiple: float = 2.0,
        min_sigma_multiple: float = 2.0,
        min_volume_ratio: float = 1.5,
        lookback_days: int = 20,
        atr_period: int = 14,
        stop_loss_candidates: list = None,
        min_holding_period: str = "1d",
        entry_timing: str = "next_open",
    ):
        self.market = market
        self.scan_mode = scan_mode
        self.scan_times = scan_times or ["15:30"]
        self.price_feed = price_feed
        self.min_atr_multiple = min_atr_multiple
        self.min_sigma_multiple = min_sigma_multiple
        self.min_volume_ratio = min_volume_ratio
        self.lookback_days = lookback_days
        self.atr_period = atr_period
        self.stop_loss_candidates = stop_loss_candidates or []
        self.min_holding_period = min_holding_period
        self.entry_timing = entry_timing


def _a_share_stop_loss_candidates() -> list:
    return [
        StopLossConfig(stop_loss_type="percent", stop_loss_value=5.0, hard_stop=True),
        StopLossConfig(stop_loss_type="percent", stop_loss_value=8.0, hard_stop=True),
        StopLossConfig(stop_loss_type="atr", stop_loss_value=2.0, hard_stop=True),
    ]


def _hk_stop_loss_candidates() -> list:
    return [
        StopLossConfig(stop_loss_type="percent", stop_loss_value=3.0, hard_stop=True),
        StopLossConfig(stop_loss_type="percent", stop_loss_value=5.0, hard_stop=True),
        StopLossConfig(stop_loss_type="atr", stop_loss_value=1.5, hard_stop=True),
    ]


def _us_stop_loss_candidates() -> list:
    return [
        StopLossConfig(stop_loss_type="percent", stop_loss_value=2.0, hard_stop=True),
        StopLossConfig(stop_loss_type="percent", stop_loss_value=4.0, hard_stop=True),
        StopLossConfig(stop_loss_type="atr", stop_loss_value=1.0, hard_stop=True),
    ]


MARKET_STRATEGIES = {
    Market.A_SHARE: MarketAnomalyStrategy(
        market=Market.A_SHARE,
        scan_mode="both",
        scan_times=["10:00", "14:00", "15:30"],
        price_feed="baostock",
        min_atr_multiple=2.0,
        min_sigma_multiple=2.0,
        min_volume_ratio=1.5,
        lookback_days=20,
        atr_period=14,
        stop_loss_candidates=_a_share_stop_loss_candidates(),
        min_holding_period="1d",
        entry_timing="next_open",
    ),
    Market.HK: MarketAnomalyStrategy(
        market=Market.HK,
        scan_mode="intraday",
        scan_times=["10:00", "14:00", "16:00"],
        price_feed="yfinance",
        min_atr_multiple=1.5,
        min_sigma_multiple=2.0,
        min_volume_ratio=1.5,
        lookback_days=20,
        atr_period=14,
        stop_loss_candidates=_hk_stop_loss_candidates(),
        min_holding_period="15m",
        entry_timing="immediate",
    ),
    Market.US: MarketAnomalyStrategy(
        market=Market.US,
        scan_mode="intraday",
        scan_times=["22:00", "01:00", "04:00"],
        price_feed="yfinance",
        min_atr_multiple=1.5,
        min_sigma_multiple=2.0,
        min_volume_ratio=1.5,
        lookback_days=20,
        atr_period=14,
        stop_loss_candidates=_us_stop_loss_candidates(),
        min_holding_period="5m",
        entry_timing="immediate",
    ),
}


def get_strategy(market: Market) -> MarketAnomalyStrategy:
    """获取市场对应的异动策略"""
    return MARKET_STRATEGIES.get(market, MARKET_STRATEGIES[Market.A_SHARE])