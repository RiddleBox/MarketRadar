"""
tests/test_realtime_paper_trading.py — 实时模拟盘端到端测试

验证：
  1. YFinanceFeed 实时行情获取
  2. CompositeFeed 多数据源 fallback
  3. PaperTrader 实时价格更新
  4. 止损/止盈触发
"""
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.schemas import (
    ActionPlan, ActionPhase, ActionType, Direction, InstrumentType,
    Market, PositionSizing, PriorityLevel, StopLossConfig, TakeProfitConfig,
)
from m9_paper_trader.paper_trader import PaperTrader
from m9_paper_trader.price_feed import (
    CompositeFeed, YFinanceFeed, AKShareRealtimeFeed, PriceSnapshot,
)


def _make_plan(instrument: str, entry_price: float, market: Market) -> ActionPlan:
    """创建测试用 ActionPlan"""
    return ActionPlan(
        opportunity_id=f"opp_realtime_{instrument}",
        plan_summary=f"BULLISH | {instrument}",
        primary_instruments=[instrument],
        instrument_type=InstrumentType.STOCK,
        direction=Direction.BULLISH,
        market=market,
        stop_loss=StopLossConfig(
            stop_loss_type="percent",
            stop_loss_value=5.0,
            hard_stop=True,
        ),
        take_profit=TakeProfitConfig(
            take_profit_type="percent",
            take_profit_value=10.0,
        ),
        position_sizing=PositionSizing(
            suggested_allocation="5%",
            max_allocation="10%",
            sizing_rationale="test",
            suggested_allocation_pct=0.05,
            max_allocation_pct=0.10,
        ),
        phases=[
            ActionPhase(
                phase_name="Phase 1",
                action_type=ActionType.BUY,
                timing_description="confirm",
                allocation_ratio=1.0,
            )
        ],
        valid_until=datetime.now() + timedelta(days=7),
        review_triggers=["7 days"],
        opportunity_priority=PriorityLevel.POSITION,
    )


class TestYFinanceFeedRealtime:
    """测试 YFinanceFeed 实时行情（需要网络）"""

    def test_yfinance_us_stock(self):
        """测试美股实时行情（AAPL）"""
        feed = YFinanceFeed()
        snapshot = feed.get_price("AAPL")
        
        # 如果触发速率限制，跳过测试
        if snapshot is None:
            print("⚠️ YFinance rate limited, skipping test")
            return
        
        assert snapshot.last > 0
        assert snapshot.instrument == "AAPL"
        print(f"✓ AAPL: ${snapshot.last:.2f}")

    def test_yfinance_hk_stock(self):
        """测试港股实时行情（腾讯 0700.HK）"""
        feed = YFinanceFeed()
        snapshot = feed.get_price("0700.HK")
        
        if snapshot is None:
            print("⚠️ YFinance rate limited, skipping test")
            return
        
        assert snapshot.last > 0
        assert snapshot.instrument == "0700.HK"
        print(f"✓ 腾讯(0700.HK): HK${snapshot.last:.2f}")

    def test_yfinance_cache(self):
        """测试 15 秒缓存机制"""
        feed = YFinanceFeed()
        
        # 第一次调用
        snapshot1 = feed.get_price("AAPL")
        if snapshot1 is None:
            print("⚠️ YFinance rate limited, skipping test")
            return
        
        # 第二次调用（应该命中缓存）
        snapshot2 = feed.get_price("AAPL")
        assert snapshot2 is not None
        assert snapshot1.last == snapshot2.last
        assert snapshot1.timestamp == snapshot2.timestamp
        print("✓ Cache hit verified")


class TestCompositeFeedRealtime:
    """测试 CompositeFeed 多数据源 fallback"""

    def test_composite_fallback_order(self):
        """测试 fallback 顺序：YFinance → AKShare"""
        # Mock YFinanceFeed 返回 None（模拟失败）
        mock_yf = MagicMock()
        mock_yf.get_price.return_value = None
        
        # Mock AKShareRealtimeFeed 返回数据
        mock_ak = MagicMock()
        mock_ak.get_price.return_value = PriceSnapshot(
            instrument="600519.SH",
            last=1800.0,
            timestamp=datetime.now(),
        )
        
        feed = CompositeFeed([mock_yf, mock_ak])
        snapshot = feed.get_price("600519.SH")
        
        assert snapshot is not None
        assert snapshot.last == 1800.0
        assert mock_yf.get_price.called
        assert mock_ak.get_price.called
        print("✓ Fallback chain works")

    def test_composite_all_fail(self):
        """测试所有数据源都失败"""
        mock_yf = MagicMock()
        mock_yf.get_price.return_value = None
        
        mock_ak = MagicMock()
        mock_ak.get_price.return_value = None
        
        feed = CompositeFeed([mock_yf, mock_ak])
        snapshot = feed.get_price("INVALID")
        
        assert snapshot is None
        print("✓ All sources failed, returns None")


class TestRealtimePaperTrading:
    """测试实时模拟盘（端到端）"""

    def test_paper_trader_with_mock_feed(self):
        """测试模拟盘 + Mock 实时行情"""
        # 创建临时文件
        tmp = Path(tempfile.mkdtemp())
        pos_file = tmp / "positions.json"
        log_file = tmp / "log.json"
        
        # Mock 价格数据源
        mock_feed = MagicMock()
        mock_feed.get_price.return_value = PriceSnapshot(
            instrument="AAPL",
            last=150.0,
            timestamp=datetime.now(),
        )
        
        # 创建模拟盘
        trader = PaperTrader(
            initial_capital=100000.0,
            position_file=pos_file,
            trade_log_file=log_file,
            price_feed=mock_feed,
        )
        
        # 创建 ActionPlan
        plan = _make_plan("AAPL", 150.0, Market.US)
        
        # 开仓
        pos = trader.open_from_plan(plan, entry_price=150.0)
        assert pos is not None
        assert pos.instrument == "AAPL"
        assert pos.entry_price == 150.0
        print(f"✓ Position opened: {pos.quantity} shares @ ${pos.entry_price}")
        
        # 更新价格（触发止盈：+10%）
        mock_feed.get_price.return_value = PriceSnapshot(
            instrument="AAPL",
            last=165.0,  # +10%
            timestamp=datetime.now(),
        )
        
        trader.update_all_positions()
        
        # 验证止盈触发
        pos = trader.get_position(pos.position_id)
        assert pos.status == "CLOSED"
        assert pos.exit_reason == "take_profit"
        print(f"✓ Take profit triggered at ${pos.exit_price}")

    def test_paper_trader_stop_loss(self):
        """测试止损触发"""
        tmp = Path(tempfile.mkdtemp())
        pos_file = tmp / "positions.json"
        log_file = tmp / "log.json"
        
        mock_feed = MagicMock()
        mock_feed.get_price.return_value = PriceSnapshot(
            instrument="AAPL",
            last=150.0,
            timestamp=datetime.now(),
        )
        
        trader = PaperTrader(
            initial_capital=100000.0,
            position_file=pos_file,
            trade_log_file=log_file,
            price_feed=mock_feed,
        )
        
        plan = _make_plan("AAPL", 150.0, Market.US)
        pos = trader.open_from_plan(plan, entry_price=150.0)
        
        # 更新价格（触发止损：-5%）
        mock_feed.get_price.return_value = PriceSnapshot(
            instrument="AAPL",
            last=142.5,  # -5%
            timestamp=datetime.now(),
        )
        
        trader.update_all_positions()
        
        # 验证止损触发
        pos = trader.get_position(pos.position_id)
        assert pos.status == "CLOSED"
        assert pos.exit_reason == "stop_loss"
        print(f"✓ Stop loss triggered at ${pos.exit_price}")


if __name__ == "__main__":
    print("Running realtime paper trading tests...\n")
    
    # YFinanceFeed 测试
    print("=== YFinanceFeed Tests ===")
    test = TestYFinanceFeedRealtime()
    test.test_yfinance_us_stock()
    test.test_yfinance_hk_stock()
    test.test_yfinance_cache()
    
    # CompositeFeed 测试
    print("\n=== CompositeFeed Tests ===")
    test2 = TestCompositeFeedRealtime()
    test2.test_composite_fallback_order()
    test2.test_composite_all_fail()
    
    # 端到端测试
    print("\n=== End-to-End Tests ===")
    test3 = TestRealtimePaperTrading()
    test3.test_paper_trader_with_mock_feed()
    test3.test_paper_trader_stop_loss()
    
    print("\n✅ All tests completed!")
