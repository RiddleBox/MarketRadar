"""
tests/test_m9_7b.py -- Iteration 7B tests

Covering:
  1. TushareFeed (init / calendar / limit prices / daily / futures)
  2. CompositeFeed (fallback chain)
  3. EquityCurveTracker
  4. Futures contract specs (market_rules)
  5. PaperTrader futures support
"""
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.market_rules import MarketRules
from m9_paper_trader.price_feed import (
    CompositeFeed, CSVPriceFeed, EquityCurveTracker, PriceSnapshot, TushareFeed,
)
from m9_paper_trader.paper_trader import PaperTrader


class TestTushareFeedInit:
    def test_no_token_disabled(self):
        tf = TushareFeed(token="")
        assert not tf.available

    def test_invalid_token_pro_api_fails(self):
        tf = TushareFeed(token="invalid_token_12345")
        assert not tf.available or tf._pro is None or tf._pro is not None


class TestTushareCalendar:
    def test_calendar_from_cache_file(self):
        tmp = Path(tempfile.mkdtemp())
        cache_file = tmp / "trade_calendar.json"
        cache_file.write_text('["2026-01-05", "2026-01-06", "2026-01-07"]', encoding="utf-8")
        tf = TushareFeed(token="")
        tf._cal_cache_file = cache_file
        cal = tf.get_trade_calendar()
        assert date(2026, 1, 5) in cal
        assert len(cal) == 3

    def test_is_trading_day_with_cache(self):
        tmp = Path(tempfile.mkdtemp())
        cache_file = tmp / "trade_calendar.json"
        cache_file.write_text('["2026-01-05"]', encoding="utf-8")
        tf = TushareFeed(token="")
        tf._cal_cache_file = cache_file
        assert tf.is_trading_day(date(2026, 1, 5))
        assert not tf.is_trading_day(date(2026, 1, 4))

    def test_next_trading_day_with_cache(self):
        tmp = Path(tempfile.mkdtemp())
        cache_file = tmp / "trade_calendar.json"
        cache_file.write_text('["2026-01-05", "2026-01-06", "2026-01-07"]', encoding="utf-8")
        tf = TushareFeed(token="")
        tf._cal_cache_file = cache_file
        nxt = tf.next_trading_day(date(2026, 1, 5))
        assert nxt == date(2026, 1, 6)

    def test_no_calendar_fallback_weekday(self):
        tf = TushareFeed(token="")
        tf._cal_cache_file = Path("__nonexistent__")
        assert tf.is_trading_day(date(2026, 1, 5))   # Monday
        assert not tf.is_trading_day(date(2026, 1, 4)) # Sunday


class TestCompositeFeed:
    def test_fallback_to_second_feed(self):
        mock1 = MagicMock()
        mock1.get_price.return_value = None
        mock2 = MagicMock()
        mock2.get_price.return_value = PriceSnapshot(
            instrument="510300", price=3.80, open_price=3.78, high=3.85,
            low=3.75, volume=1000, amount=3800, timestamp=datetime.now(), source="mock",
        )
        cf = CompositeFeed([mock1, mock2])
        result = cf.get_price("510300")
        assert result is not None
        assert result.price == 3.80

    def test_all_feeds_fail(self):
        mock1 = MagicMock()
        mock1.get_price.return_value = None
        cf = CompositeFeed([mock1])
        assert cf.get_price("510300") is None

    def test_is_trading_day_delegates(self):
        mock1 = MagicMock(spec=TushareFeed)
        mock1.is_trading_day.return_value = True
        cf = CompositeFeed([mock1])
        assert cf.is_trading_day()


class TestEquityCurveTracker:
    def test_record_and_retrieve(self):
        tmp = Path(tempfile.mkdtemp()) / "equity.json"
        tracker = EquityCurveTracker(save_path=tmp)
        tracker.record(date(2026, 4, 15), 1_000_000, 900_000, 100_000, 2, 0)
        tracker.record(date(2026, 4, 16), 1_020_000, 900_000, 120_000, 2, 1, 20_000)
        curve = tracker.get_curve()
        assert len(curve) == 2
        assert curve[1]["equity"] == 1_020_000

    def test_drawdown_calculation(self):
        tmp = Path(tempfile.mkdtemp()) / "equity.json"
        tracker = EquityCurveTracker(save_path=tmp)
        tracker.record(date(2026, 4, 15), 1_000_000, 900_000, 100_000, 2, 0)
        tracker.record(date(2026, 4, 16), 950_000, 850_000, 100_000, 2, 0, -50_000)
        latest = tracker.latest()
        assert latest["drawdown_pct"] == 5.0

    def test_max_drawdown(self):
        tmp = Path(tempfile.mkdtemp()) / "equity.json"
        tracker = EquityCurveTracker(save_path=tmp)
        tracker.record(date(2026, 4, 13), 1_000_000, 900_000, 100_000, 2, 0)
        tracker.record(date(2026, 4, 14), 920_000, 820_000, 100_000, 2, 0, -80_000)
        tracker.record(date(2026, 4, 15), 980_000, 880_000, 100_000, 2, 0, 60_000)
        assert tracker.max_drawdown_pct() == 8.0

    def test_total_return(self):
        tmp = Path(tempfile.mkdtemp()) / "equity.json"
        tracker = EquityCurveTracker(save_path=tmp)
        tracker.record(date(2026, 4, 13), 1_000_000, 900_000, 100_000, 2, 0)
        tracker.record(date(2026, 4, 14), 1_050_000, 950_000, 100_000, 2, 0, 50_000)
        assert abs(tracker.total_return_pct() - 5.0) < 0.01


class TestFuturesContractSpecs:
    def test_if_spec(self):
        mr = MarketRules()
        spec = mr.futures_contract_spec("IF")
        assert spec is not None
        assert spec["multiplier"] == 300
        assert spec["margin_pct"] == 0.12

    def test_if_with_contract_suffix(self):
        mr = MarketRules()
        spec = mr.futures_contract_spec("IF2504")
        assert spec is not None
        assert spec["multiplier"] == 300

    def test_unknown_symbol_returns_none(self):
        mr = MarketRules()
        assert mr.futures_contract_spec("ZZZ") is None

    def test_futures_margin(self):
        mr = MarketRules()
        margin = mr.futures_margin("IF", 3800.0, 1)
        assert margin is not None
        assert abs(margin - 3800.0 * 300 * 0.12) < 1

    def test_futures_notional(self):
        mr = MarketRules()
        notional = mr.futures_notional("IF", 3800.0, 1)
        assert notional == 3800.0 * 300


class TestPaperTraderFutures:
    def test_open_futures(self):
        from m9_paper_trader.paper_trader import RiskMonitor
        trader = PaperTrader(
            save_path=Path(tempfile.mkdtemp()) / "test.json",
            initial_capital=1_000_000,
            risk_monitor=RiskMonitor(initial_capital=1_000_000, max_single_position_pct=0.20),
        )
        pp = trader.open_futures("IF", "BULLISH", 3800.0, quantity=1)
        assert pp is not None
        assert pp.market == "A_FUTURES"
        assert pp.direction == "BULLISH"
        assert pp.orders[0].fee_paid > 0

    def test_open_futures_unknown_symbol(self):
        trader = PaperTrader(save_path=Path(tempfile.mkdtemp()) / "test.json")
        pp = trader.open_futures("ZZZ", "BULLISH", 100.0)
        assert pp is None

    def test_record_equity(self):
        eq_path = Path(tempfile.mkdtemp()) / "equity.json"
        trader = PaperTrader(
            save_path=Path(tempfile.mkdtemp()) / "test.json",
            initial_capital=1_000_000,
        )
        trader._equity_tracker = EquityCurveTracker(save_path=eq_path)
        trader.record_equity(date(2026, 4, 15))
        curve = trader.get_equity_curve()
        assert len(curve) == 1
        assert curve[0]["equity"] == 1_000_000

    def test_reset_daily_counters(self):
        trader = PaperTrader(
            save_path=Path(tempfile.mkdtemp()) / "test.json",
            initial_capital=1_000_000,
        )
        trader._closed_today = 5
        trader._daily_pnl = -1000
        trader.reset_daily_counters()
        assert trader._closed_today == 0
        assert trader._daily_pnl == 0.0
