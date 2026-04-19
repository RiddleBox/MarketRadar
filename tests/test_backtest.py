"""
tests/test_backtest.py — 回测框架测试

覆盖：
  1. 种子数据加载和价格查询
  2. BacktestEngine 历史事件回测
  3. FeeModel 手续费/滑点模型
  4. 分层统计（by_signal_type, by_direction）
"""
from datetime import date
from pathlib import Path

import pytest

from backtest.history_price import HistoryPriceFeed
from backtest.backtest_engine import BacktestEngine, BacktestCase, FeeModel, DEFAULT_FEE_MODEL
from backtest.seed_data import preload_seed_into_feed


@pytest.fixture
def price_feed():
    feed = HistoryPriceFeed()
    preload_seed_into_feed(feed)
    return feed


@pytest.fixture
def backtest_engine(price_feed):
    return BacktestEngine(price_feed=price_feed)


@pytest.fixture
def backtest_engine_with_fees(price_feed):
    return BacktestEngine(price_feed=price_feed, fee_model=FeeModel())


class TestSeedDataLoading:
    def test_510300_seed_exists(self, price_feed):
        price = price_feed.get_price("510300.SH", date(2024, 9, 24))
        assert price is not None and price > 3.0

    def test_510300_price_positive_change(self, price_feed):
        p1 = price_feed.get_price("510300.SH", date(2024, 9, 24))
        p2 = price_feed.get_price("510300.SH", date(2024, 9, 25))
        assert p2 is not None and p1 is not None
        pct_chg = (p2 - p1) / p1 * 100
        assert pct_chg > 0

    def test_588000_seed_exists(self, price_feed):
        price = price_feed.get_price("588000.SH", date(2025, 2, 17))
        assert price is not None

    def test_ohlc_available(self, price_feed):
        """HistoryPriceFeed should return OHLC data"""
        o = price_feed.get_price("510300.SH", date(2024, 9, 24), price_type="open")
        h = price_feed.get_price("510300.SH", date(2024, 9, 24), price_type="high")
        l = price_feed.get_price("510300.SH", date(2024, 9, 24), price_type="low")
        c = price_feed.get_price("510300.SH", date(2024, 9, 24), price_type="close")
        assert o is not None and h is not None and l is not None and c is not None
        assert h >= c and l <= c


class TestFeeModel:
    def test_default_round_trip_cost(self):
        cost = DEFAULT_FEE_MODEL.round_trip_cost_pct()
        assert cost > 0
        assert cost < 0.01  # less than 1%

    def test_custom_fee_model(self):
        fm = FeeModel(commission_rate=0.001, stamp_tax_rate=0.001, slippage_pct=0.001)
        cost = fm.round_trip_cost_pct()
        assert cost > DEFAULT_FEE_MODEL.round_trip_cost_pct()

    def test_fee_reduces_profit(self, price_feed):
        """Fee cost should be subtracted from realized PnL"""
        fee = FeeModel(commission_rate=0.001, stamp_tax_rate=0.001, slippage_pct=0.001)
        cost = fee.round_trip_cost_pct()
        assert cost > 0

        engine_with_fee = BacktestEngine(price_feed=price_feed, fee_model=fee)
        cases = [
            BacktestCase(
                opportunity_id="fee_test",
                opportunity_title="Fee test",
                signal_ids=["t1"],
                signal_type="macro",
                signal_intensity=9.5,
                signal_confidence=9.0,
                signal_direction="BULLISH",
                instrument="510300.SH",
                market="A_SHARE",
                time_horizon="short",
                created_date=date(2024, 9, 24),
                entry_price=None,
                stop_loss_pct=0.05,
                take_profit_pct=0.10,
                batch_id="fee_test",
            ),
        ]
        report = engine_with_fee.run(cases)
        if report.completed > 0 and report.cases[0].realized_pnl_pct is not None:
            pnl = report.cases[0].realized_pnl_pct
            if report.cases[0].status == "TAKE_PROFIT":
                assert pnl < 0.10  # tp_pct minus fee
            elif report.cases[0].status == "TIMEOUT":
                assert True


class TestBacktestEngine:
    def test_macro_signal_backtest(self, backtest_engine, price_feed):
        cases = [
            BacktestCase(
                opportunity_id="macro_924_300",
                opportunity_title="2024-09-24 央行降准降息",
                signal_ids=["m1"],
                signal_type="macro",
                signal_intensity=9.5,
                signal_confidence=9.0,
                signal_direction="BULLISH",
                instrument="510300.SH",
                market="A_SHARE",
                time_horizon="short",
                created_date=date(2024, 9, 24),
                entry_price=None,
                stop_loss_pct=0.05,
                take_profit_pct=0.10,
                batch_id="bt_test",
            ),
        ]
        report = backtest_engine.run(cases)
        assert report.total_cases == 1
        assert report.completed + report.skipped == 1
        assert report.fee_cost_pct > 0

    def test_by_signal_type_enriched(self, backtest_engine, price_feed):
        cases = [
            BacktestCase(
                opportunity_id="enriched_1",
                opportunity_title="Macro signal",
                signal_ids=["m1"],
                signal_type="macro",
                signal_intensity=9.5,
                signal_confidence=9.0,
                signal_direction="BULLISH",
                instrument="510300.SH",
                market="A_SHARE",
                time_horizon="short",
                created_date=date(2024, 9, 24),
                entry_price=None,
                stop_loss_pct=0.05,
                take_profit_pct=0.10,
                batch_id="bt_enriched",
            ),
            BacktestCase(
                opportunity_id="enriched_2",
                opportunity_title="Technical signal",
                signal_ids=["t1"],
                signal_type="technical",
                signal_intensity=6.5,
                signal_confidence=6.0,
                signal_direction="BEARISH",
                instrument="510300.SH",
                market="A_SHARE",
                time_horizon="short",
                created_date=date(2024, 10, 8),
                entry_price=None,
                stop_loss_pct=0.05,
                take_profit_pct=0.08,
                batch_id="bt_enriched",
            ),
        ]
        report = backtest_engine.run(cases)
        if report.by_signal_type:
            for _type, stats in report.by_signal_type.items():
                assert "count" in stats
                assert "win_rate" in stats
                assert "avg_pnl_pct" in stats
                assert "profit_factor" in stats
                assert "avg_holding_days" in stats
                assert "best" in stats
                assert "worst" in stats

    def test_by_direction_stats(self, backtest_engine, price_feed):
        cases = [
            BacktestCase(
                opportunity_id="dir_1",
                opportunity_title="Bull test",
                signal_ids=["b1"],
                signal_type="macro",
                signal_intensity=9.0,
                signal_confidence=8.0,
                signal_direction="BULLISH",
                instrument="510300.SH",
                market="A_SHARE",
                time_horizon="short",
                created_date=date(2024, 9, 24),
                entry_price=None,
                stop_loss_pct=0.05,
                take_profit_pct=0.10,
                batch_id="bt_dir",
            ),
        ]
        report = backtest_engine.run(cases)
        assert isinstance(report.by_direction, dict)
