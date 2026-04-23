"""
tests/test_yfinance_feed.py -- YFinanceFeed 单元测试
"""
import pytest
from datetime import date, datetime
from m9_paper_trader.price_feed import YFinanceFeed, PriceSnapshot


class TestYFinanceFeed:
    """YFinanceFeed 测试"""

    def test_convert_symbol_a_share_sh(self):
        """测试 A股上交所代码转换"""
        feed = YFinanceFeed()
        assert feed._convert_symbol("600519.SH") == "600519.SS"
        assert feed._convert_symbol("510050.SH") == "510050.SS"

    def test_convert_symbol_a_share_sz(self):
        """测试 A股深交所代码转换"""
        feed = YFinanceFeed()
        assert feed._convert_symbol("000858.SZ") == "000858.SZ"
        assert feed._convert_symbol("300750.SZ") == "300750.SZ"

    def test_convert_symbol_hk(self):
        """测试港股代码转换（去掉前导0）"""
        feed = YFinanceFeed()
        assert feed._convert_symbol("0700.HK") == "700.HK"
        assert feed._convert_symbol("09988.HK") == "9988.HK"
        assert feed._convert_symbol("00001.HK") == "1.HK"

    def test_convert_symbol_us(self):
        """测试美股代码转换（去掉后缀）"""
        feed = YFinanceFeed()
        assert feed._convert_symbol("AAPL.US") == "AAPL"
        assert feed._convert_symbol("TSLA.US") == "TSLA"

    def test_convert_symbol_no_suffix(self):
        """测试无后缀代码（保持原样）"""
        feed = YFinanceFeed()
        assert feed._convert_symbol("AAPL") == "AAPL"
        assert feed._convert_symbol("MSFT") == "MSFT"

    @pytest.mark.skip(reason="需要网络连接，跳过 CI")
    def test_get_realtime_hk_stock(self):
        """测试获取港股实时行情（腾讯）"""
        feed = YFinanceFeed()
        snap = feed.get_price("0700.HK")
        
        assert snap is not None
        assert snap.instrument == "0700.HK"
        assert snap.price > 0
        assert snap.source == "yfinance_realtime"
        assert isinstance(snap.timestamp, datetime)

    @pytest.mark.skip(reason="需要网络连接，跳过 CI")
    def test_get_realtime_us_stock(self):
        """测试获取美股实时行情（苹果）"""
        feed = YFinanceFeed()
        snap = feed.get_price("AAPL.US")
        
        assert snap is not None
        assert snap.instrument == "AAPL.US"
        assert snap.price > 0
        assert snap.source == "yfinance_realtime"

    @pytest.mark.skip(reason="需要网络连接，跳过 CI")
    def test_get_realtime_a_share(self):
        """测试获取A股实时行情（茅台）"""
        feed = YFinanceFeed()
        snap = feed.get_price("600519.SH")
        
        # yfinance 对 A股支持可能不稳定，允许返回 None
        if snap is not None:
            assert snap.instrument == "600519.SH"
            assert snap.price > 0
            assert snap.source == "yfinance_realtime"

    @pytest.mark.skip(reason="需要网络连接，跳过 CI")
    def test_get_daily_hk_stock(self):
        """测试获取港股历史数据"""
        feed = YFinanceFeed()
        snap = feed.get_price("0700.HK", dt=date(2024, 1, 2))
        
        assert snap is not None
        assert snap.instrument == "0700.HK"
        assert snap.price > 0
        assert snap.source == "yfinance_daily"

    @pytest.mark.skip(reason="需要网络连接，跳过 CI")
    def test_get_daily_us_stock(self):
        """测试获取美股历史数据"""
        feed = YFinanceFeed()
        snap = feed.get_price("AAPL.US", dt=date(2024, 1, 2))
        
        assert snap is not None
        assert snap.instrument == "AAPL.US"
        assert snap.price > 0
        assert snap.source == "yfinance_daily"

    def test_get_price_invalid_symbol(self):
        """测试无效股票代码"""
        feed = YFinanceFeed()
        snap = feed.get_price("INVALID_SYMBOL_12345")
        
        # 无效代码应该返回 None
        assert snap is None

    def test_price_snapshot_structure(self):
        """测试 PriceSnapshot 数据结构"""
        feed = YFinanceFeed()
        
        # 使用一个已知的股票代码（跳过网络测试）
        # 这里只测试数据结构，不测试实际数据
        snap = PriceSnapshot(
            instrument="TEST.HK",
            price=100.0,
            open_price=99.0,
            high=101.0,
            low=98.0,
            volume=1000000,
            amount=0.0,
            timestamp=datetime.now(),
            source="yfinance_realtime",
            prev_close=99.5,
            change_pct=0.5,
        )
        
        assert snap.instrument == "TEST.HK"
        assert snap.price == 100.0
        assert snap.source == "yfinance_realtime"
        assert snap.prev_close == 99.5
        assert snap.change_pct == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
