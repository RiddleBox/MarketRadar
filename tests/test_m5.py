"""
tests/test_m5.py — M5 持仓管理测试

覆盖：
  1. 开仓/止损/止盈条件检查
  2. 持仓状态枚举值
"""
from datetime import datetime

from core.schemas import Position, PositionStatus, Direction, Market, InstrumentType


class TestPosition:
    def test_open_position(self):
        pos = Position(
            plan_id="plan_001",
            opportunity_id="opp_001",
            instrument="510300.SH",
            instrument_type=InstrumentType.ETF,
            market=Market.A_SHARE,
            direction=Direction.BULLISH,
            quantity=10000.0,
            entry_price=3.80,
            stop_loss_price=3.61,
            take_profit_price=4.18,
            total_cost=38000,
            realized_pnl=0,
            status=PositionStatus.OPEN,
            entry_time=datetime.now(),
            updates=[],
        )
        assert pos.status == PositionStatus.OPEN
        assert pos.instrument == "510300.SH"

    def test_stop_loss_price_check(self):
        pos = Position(
            plan_id="plan_002",
            opportunity_id="opp_002",
            instrument="510300.SH",
            instrument_type=InstrumentType.ETF,
            market=Market.A_SHARE,
            direction=Direction.BULLISH,
            quantity=10000.0,
            entry_price=3.80,
            stop_loss_price=3.61,
            take_profit_price=4.18,
            total_cost=38000,
            realized_pnl=-0.0526,
            status=PositionStatus.STOP_LOSS,
            entry_time=datetime.now(),
            exit_price=3.60,
            exit_reason="止损触发",
            updates=[],
        )
        assert pos.status == PositionStatus.STOP_LOSS
        assert pos.exit_price <= pos.stop_loss_price

    def test_take_profit_price_check(self):
        pos = Position(
            plan_id="plan_003",
            opportunity_id="opp_003",
            instrument="510300.SH",
            instrument_type=InstrumentType.ETF,
            market=Market.A_SHARE,
            direction=Direction.BULLISH,
            quantity=10000.0,
            entry_price=3.80,
            stop_loss_price=3.61,
            take_profit_price=4.18,
            total_cost=38000,
            realized_pnl=0.1053,
            status=PositionStatus.TAKE_PROFIT,
            entry_time=datetime.now(),
            exit_price=4.20,
            exit_reason="止盈触发",
            updates=[],
        )
        assert pos.status == PositionStatus.TAKE_PROFIT
        assert pos.exit_price >= pos.take_profit_price
