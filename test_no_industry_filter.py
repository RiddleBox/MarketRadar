#!/usr/bin/env python3
"""测试关闭行业过滤后的股票数量"""

import sys
sys.path.insert(0, '.')

from m12_opportunity_catcher.stock_universe import StockUniverse
from core.schemas import Market

def test_no_industry_filter():
    """测试关闭行业过滤"""
    print("Testing with industry filter DISABLED (all industries, price>$20, volume>100k)...\n")

    # 创建股票池管理器，关闭行业过滤，保留价格过滤
    universe = StockUniverse(
        enable_industry_filter=False,
        min_price_us=20.0,
        min_volume=100000
    )

    # 测试美股
    us_stocks = universe.get_stock_list(Market.US, force_refresh=True)
    print(f"Filtered US stocks (all industries): {len(us_stocks)}")
    print(f"First 20: {us_stocks[:20]}\n")

    # 测试A股
    a_stocks = universe.get_stock_list(Market.A_SHARE, force_refresh=True)
    print(f"Filtered A-share stocks (all industries): {len(a_stocks)}")
    print(f"First 20: {a_stocks[:20]}")

if __name__ == "__main__":
    test_no_industry_filter()
