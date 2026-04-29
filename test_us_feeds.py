#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试美股数据源"""

from m9_paper_trader.price_feed import YFinanceFeed

print("=== Testing US Stock Data Feeds ===\n")

# Test YFinance
print("1. YFinance (free, 15min delay):")
try:
    yf = YFinanceFeed()
    price = yf.get_price('AAPL.US')
    if price and price.price > 0:
        print(f"   [OK] AAPL: ${price.price:.2f}")
        print(f"   Change: {price.change_pct:.2f}%")
    else:
        print("   [FAIL] No data returned")
except Exception as e:
    print(f"   [ERROR] {e}")

print()
print("2. FutuFeed (requires futu-api + OpenD):")
try:
    from futu import OpenQuoteContext
    print("   [OK] futu-api installed")
    print("   Note: Requires OpenD running locally on port 11111")
    print("   Free tier: 15min delay for US stocks")
except ImportError:
    print("   [NOT INSTALLED] Install: pip install futu-api")

print()
print("3. YFinance Rate Limits:")
print("   - Free tier: 2,000 requests/hour")
print("   - ~33 requests/minute")
print("   - For continuous monitoring, this is sufficient")
print("   - Our system: ~10 stocks scanned every 10min = 60 req/hour")
