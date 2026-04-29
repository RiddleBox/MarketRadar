#!/usr/bin/env python3
"""测试股票池过滤功能"""

import sys
sys.path.insert(0, 'd:/AIProjects/MarketRadar')

from m12_opportunity_catcher.stock_universe import get_stock_universe
from core.schemas import Market

print("Testing filters (tech industry + price>$20 + volume>100k)...")
print()

# 测试美股过滤
stocks = get_stock_universe().get_stock_list(Market.US, force_refresh=True)
print(f"Filtered US stocks: {len(stocks)}")
print(f"First 20: {stocks[:20]}")
print()

# 测试A股过滤
stocks_cn = get_stock_universe().get_stock_list(Market.A_SHARE, force_refresh=True)
print(f"Filtered A-share stocks: {len(stocks_cn)}")
print(f"First 20: {stocks_cn[:20]}")
