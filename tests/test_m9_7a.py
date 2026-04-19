"""
tests/test_m9_7a.py — Iteration 7A 模拟盘核心增强测试

覆盖：
  1. FeeModel 共享 (core/fee_model.py)
  2. MarketRules (core/market_rules.py)
  3. OrderState + PaperOrder
  4. RiskMonitor 风控
  5. PaperTrader 增强功能（手续费/订单/风控/市场规则）
  6. Trade log 审计
"""
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from core.fee_model import FeeModel, DEFAULT_FEE_MODEL
from core.market_rules import MarketRules, OrderStatus
from core.schemas import (
    ActionPlan, ActionPhase, ActionType, Direction, InstrumentType,
    Market, OpportunityObject, OpportunityScore, PositionSizing,
    PriorityLevel, StopLossConfig, TakeProfitConfig, TimeWindow,
)
from m9_paper_trader.paper_trader import PaperTrader, PaperPosition, PaperOrder, RiskMonitor


def _make_plan(entry_price: float = 3.80) -> ActionPlan:
    return ActionPlan(
        opportunity_id="opp_7a_test",
        plan_summary="BULLISH | 510300.SH",
        primary_instruments=["510300.SH"],
        instrument_type=InstrumentType.ETF,
        direction=Direction.BULLISH,
        market=Market.A_SHARE,
        stop_loss=StopLossConfig(stop_loss_type="percent", stop_loss_value=5.0, hard_stop=True),
        take_profit=TakeProfitConfig(take_profit_type="percent", take_profit_value=10.0),
        position_sizing=PositionSizing(
            suggested_allocation="5%", max_allocation="10%",
            sizing_rationale="test", suggested_allocation_pct=0.05, max_allocation_pct=0.10,
        ),
        phases=[ActionPhase(phase_name="Phase 1", action_type=ActionType.BUY,
                             timing_description="confirm", allocation_ratio=1.0)],
        valid_until=datetime.now() + timedelta(days=7),
        review_triggers=["7 days"],
        opportunity_priority=PriorityLevel.POSITION,
    )


class TestFeeModel:
    def test_buy_cost(self):
        fm = FeeModel()
        cost = fm.buy_cost(100_000)
        assert cost > 0
        assert cost == max(100_000 * 0.0003, 5.0) + 100_000 * 0.0005

    def test_sell_cost(self):
        fm = FeeModel()
        cost = fm.sell_cost(100_000)
        assert cost > fm.buy_cost(100_000)  # sell includes stamp tax

    def test_round_trip_cost_pct(self):
        fm = FeeModel()
        pct = fm.round_trip_cost_pct()
        assert abs(pct - (0.0003 * 2 + 0.001 + 0.0005 * 2)) < 1e-9

    def test_min_commission(self):
        fm = FeeModel()
        cost = fm.buy_cost(100)
        assert cost >= 5.0

    def test_default_fee_model_exists(self):
        assert DEFAULT_FEE_MODEL is not None
        assert DEFAULT_FEE_MODEL.round_trip_cost_pct() > 0


class TestMarketRules:
    def test_t1_cannot_sell_same_day(self):
        mr = MarketRules()
        assert not mr.can_sell("A_SHARE", date(2026, 4, 17), date(2026, 4, 17))

    def test_t1_can_sell_next_day(self):
        mr = MarketRules()
        assert mr.can_sell("A_SHARE", date(2026, 4, 17), date(2026, 4, 18))

    def test_futures_t0_can_sell_anytime(self):
        mr = MarketRules()
        assert mr.can_sell("A_FUTURES", date(2026, 4, 17), date(2026, 4, 17))

    def test_hk_t2_can_sell(self):
        mr = MarketRules()
        assert mr.can_sell("HK", date(2026, 4, 17), date(2026, 4, 17))

    def test_limit_up_main_board(self):
        mr = MarketRules()
        lu = mr.limit_up_price("A_SHARE", 10.0, "main")
        assert abs(lu - 11.0) < 0.01

    def test_limit_down_main_board(self):
        mr = MarketRules()
        ld = mr.limit_down_price("A_SHARE", 10.0, "main")
        assert abs(ld - 9.0) < 0.01

    def test_limit_up_gem_20pct(self):
        mr = MarketRules()
        lu = mr.limit_up_price("A_SHARE", 10.0, "gem")
        assert abs(lu - 12.0) < 0.01

    def test_limit_up_st_5pct(self):
        mr = MarketRules()
        lu = mr.limit_up_price("A_SHARE", 5.0, "st")
        assert abs(lu - 5.25) < 0.01

    def test_hk_no_limit(self):
        mr = MarketRules()
        assert mr.limit_up_price("HK", 100.0) is None
        assert mr.limit_down_price("HK", 100.0) is None

    def test_validate_price_within_limit(self):
        mr = MarketRules()
        assert mr.validate_price_within_limit("A_SHARE", 10.5, 10.0, "main")
        assert not mr.validate_price_within_limit("A_SHARE", 11.5, 10.0, "main")
        assert not mr.validate_price_within_limit("A_SHARE", 8.5, 10.0, "main")

    def test_min_lot_size(self):
        mr = MarketRules()
        assert mr.min_lot_size("A_SHARE") == 100
        assert mr.min_lot_size("HK") == 1
        assert mr.min_lot_size("A_FUTURES") == 1

    def test_round_quantity(self):
        mr = MarketRules()
        assert mr.round_quantity("A_SHARE", 250) == 200
        assert mr.round_quantity("A_SHARE", 300) == 300
        assert mr.round_quantity("HK", 150) == 150

    def test_validate_order_reject_t1_sell(self):
        mr = MarketRules()
        ok, reason = mr.validate_order(
            "A_SHARE", "SELL", 100, 10.0, 10.0, date.today(), "main", date.today()
        )
        assert not ok
        assert "T+1" in reason

    def test_validate_order_reject_price_outside_limit(self):
        mr = MarketRules()
        ok, reason = mr.validate_order(
            "A_SHARE", "BUY", 100, 12.0, 10.0, date.today(), "main", date.today()
        )
        assert not ok

    def test_validate_order_accept_valid(self):
        mr = MarketRules()
        ok, reason = mr.validate_order(
            "A_SHARE", "BUY", 100, 10.5, 10.0, date.today(), "main", date.today()
        )
        assert ok


class TestOrderStatus:
    def test_four_states(self):
        assert OrderStatus.SUBMITTED.value == "SUBMITTED"
        assert OrderStatus.FILLED.value == "FILLED"
        assert OrderStatus.CANCELLED.value == "CANCELLED"
        assert OrderStatus.REJECTED.value == "REJECTED"


class TestPaperOrder:
    def test_initial_status(self):
        order = PaperOrder("510300", "A_SHARE", "BUY", 100, 3.80)
        assert order.status == OrderStatus.SUBMITTED.value
        assert order.order_id.startswith("ord_")

    def test_to_dict(self):
        order = PaperOrder("510300", "A_SHARE", "BUY", 100, 3.80)
        d = order.to_dict()
        assert d["instrument"] == "510300"
        assert d["status"] == "SUBMITTED"


class TestRiskMonitor:
    def test_allow_normal_open(self):
        rm = RiskMonitor()
        allowed, _ = rm.check_before_open(50_000, 1_000_000)
        assert allowed

    def test_reject_oversized_position(self):
        rm = RiskMonitor(max_single_position_pct=0.05)
        allowed, reason = rm.check_before_open(100_000, 1_000_000)
        assert not allowed
        assert "single position" in reason

    def test_halt_on_total_drawdown(self):
        rm = RiskMonitor(max_total_drawdown_pct=0.10)
        rm._peak_equity = 1_000_000
        allowed, reason = rm.check_before_open(10_000, 890_000)
        assert not allowed
        assert "total drawdown" in reason

    def test_halt_on_daily_drawdown(self):
        rm = RiskMonitor(max_daily_drawdown_pct=0.05)
        rm.reset_daily(1_000_000)
        allowed, reason = rm.check_before_open(10_000, 940_000)
        assert not allowed
        assert "daily drawdown" in reason

    def test_halted_stays_halted(self):
        rm = RiskMonitor(max_total_drawdown_pct=0.10)
        rm._peak_equity = 1_000_000
        rm._trading_halted = True
        allowed, reason = rm.check_before_open(10_000, 1_000_000)
        assert not allowed

    def test_compute_equity(self):
        rm = RiskMonitor()
        pp = PaperPosition("p1", "o1", [], "510300", "A_SHARE", "BULLISH",
                           3.80, 3.50, 4.20, 1000)
        pp.current_price = 4.00
        equity = rm.compute_equity([pp], 100_000)
        expected = 100_000 + (4.00 - 3.80) * 1000
        assert abs(equity - expected) < 0.01


class TestPortfolioRisk:
    def _make_position(self, instrument, notional, direction="BULLISH"):
        p = PaperPosition(
            f"p_{instrument}", "o1", [], instrument, "A_SHARE", direction,
            3.80, 3.50, 4.20, int(notional / 3.80),
        )
        p.current_price = 3.80
        return p

    def test_total_exposure_warning(self):
        rm = RiskMonitor(initial_capital=1_000_000, max_total_exposure_pct=0.30)
        positions = [
            self._make_position("510300.SH", 150_000),
            self._make_position("588000.SH", 120_000),
            self._make_position("000001.SZ", 80_000),
        ]
        warnings = rm.check_portfolio_risk(positions)
        total_pct = sum(p.current_price * p.quantity for p in positions) / 1_000_000
        if total_pct > 0.30:
            assert any("总仓位" in w for w in warnings)
        else:
            assert not any("总仓位" in w for w in warnings)

    def test_theme_exposure_warning(self):
        rm = RiskMonitor(initial_capital=1_000_000, max_theme_exposure_pct=0.15)
        positions = [
            self._make_position("510300.SH", 100_000),
            self._make_position("000001.SZ", 80_000),
        ]
        theme_map = {"510300.SH": "大盘蓝筹", "000001.SZ": "大盘蓝筹"}
        warnings = rm.check_portfolio_risk(positions, theme_map=theme_map)
        assert any("大盘蓝筹" in w for w in warnings)

    def test_high_correlation_warning(self):
        rm = RiskMonitor(initial_capital=1_000_000, high_corr_threshold=0.85)
        existing = [self._make_position("510300.SH", 80_000)]
        new_pos = self._make_position("588000.SH", 80_000)
        corr_matrix = {"588000.SH": {"510300.SH": 0.92}}
        warnings = rm.check_portfolio_risk(
            existing, new_position=new_pos, corr_matrix=corr_matrix
        )
        assert any("高相关" in w for w in warnings)

    def test_no_warning_when_within_limits(self):
        rm = RiskMonitor(initial_capital=1_000_000, max_total_exposure_pct=0.30, max_theme_exposure_pct=0.15)
        positions = [self._make_position("510300.SH", 50_000)]
        warnings = rm.check_portfolio_risk(positions)
        assert not any("总仓位" in w for w in warnings)


class TestPaperTraderEnhanced:
    def test_open_from_plan_with_entry_price(self):
        trader = PaperTrader(save_path=Path(tempfile.mkdtemp()) / "test_pos.json")
        plan = _make_plan()
        opened = trader.open_from_plan(plan, ["sig_1"], "opp_1", entry_price=3.80, prev_close=3.78)
        assert len(opened) == 1
        assert opened[0].entry_price == 3.80
        assert opened[0].entry_price > 0
        assert opened[0].orders[0].status == OrderStatus.FILLED.value
        assert opened[0].fee_paid > 0

    def test_open_from_plan_rejects_zero_price(self):
        trader = PaperTrader(save_path=Path(tempfile.mkdtemp()) / "test_pos.json")
        plan = _make_plan()
        opened = trader.open_from_plan(plan, ["sig_1"], "opp_1", entry_price=0.0)
        assert len(opened) == 0

    def test_position_fee_deducted_on_close(self):
        trader = PaperTrader(save_path=Path(tempfile.mkdtemp()) / "test_pos.json")
        plan = _make_plan()
        opened = trader.open_from_plan(plan, ["sig_1"], "opp_1", entry_price=3.80)
        pp = opened[0]
        trader.update_price(pp.paper_position_id, 4.18)
        assert pp.status == "TAKE_PROFIT"
        assert pp.realized_pnl_after_fees is not None
        assert pp.realized_pnl_after_fees < pp.realized_pnl_pct

    def test_manual_open_validates_market_rules(self):
        trader = PaperTrader(save_path=Path(tempfile.mkdtemp()) / "test_pos.json")
        pp = trader.open_manual("510300", "A_SHARE", "BULLISH", 3.80, 3.50, 4.20, 100, prev_close=3.78)
        assert pp is not None
        assert pp.quantity == 100
        assert pp.orders[0].status == OrderStatus.FILLED.value

    def test_t1_sell_rejected(self):
        trader = PaperTrader(save_path=Path(tempfile.mkdtemp()) / "test_pos.json")
        pp = trader.open_manual("510300", "A_SHARE", "BEARISH", 3.80, 4.20, None, 100,
                                prev_close=3.78)
        assert pp is None

    def test_trade_log_recorded(self):
        trader = PaperTrader(save_path=Path(tempfile.mkdtemp()) / "test_pos.json")
        plan = _make_plan()
        trader.open_from_plan(plan, ["sig_1"], "opp_1", entry_price=3.80)
        assert len(trader._trade_log) >= 1
        assert trader._trade_log[0]["event"] == "OPEN"

    def test_on_position_closed_callback(self):
        closed_ids = []
        def callback(pp):
            closed_ids.append(pp.paper_position_id)

        trader = PaperTrader(
            save_path=Path(tempfile.mkdtemp()) / "test_pos.json",
            on_position_closed=callback,
        )
        plan = _make_plan()
        opened = trader.open_from_plan(plan, ["sig_1"], "opp_1", entry_price=3.80)
        pp = opened[0]
        trader.update_price(pp.paper_position_id, 3.50)
        assert pp.status == "STOP_LOSS"
        assert len(closed_ids) == 1

    def test_risk_monitor_integrated(self):
        trader = PaperTrader(save_path=Path(tempfile.mkdtemp()) / "test_pos.json")
        trader._risk_monitor = RiskMonitor(max_single_position_pct=0.01)
        plan = _make_plan()
        opened = trader.open_from_plan(plan, ["sig_1"], "opp_1", entry_price=3.80)
        assert len(opened) == 0
