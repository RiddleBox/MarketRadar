#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试Futu OpenD连接和美股数据"""

from m9_paper_trader.futu_feed import FutuFeed

print("=== Testing Futu OpenD Connection ===\n")

print("1. Attempting to connect to OpenD (127.0.0.1:11111)...")
try:
    futu = FutuFeed(host="127.0.0.1", port=11111)

    if futu._connected:
        print("   [OK] Connected to OpenD\n")

        print("2. Testing US stock data (AAPL.US):")
        price = futu.get_price('AAPL.US')
        if price and price.price > 0:
            print(f"   [OK] AAPL: ${price.price:.2f}")
            print(f"   Change: {price.change_pct:.2f}%")
            print(f"   Note: Free tier = 15min delay for US stocks")
        else:
            print("   [FAIL] No data returned")

        print("\n3. Testing batch query:")
        prices = futu.get_prices(['AAPL.US', 'TSLA.US', 'MSFT.US'])
        if prices:
            print(f"   [OK] Got {len(prices)} prices")
            for symbol, p in prices.items():
                if p:
                    print(f"   - {symbol}: ${p.price:.2f}")
        else:
            print("   [FAIL] Batch query failed")
    else:
        print("   [FAIL] Cannot connect to OpenD")
        print("\n   To fix:")
        print("   1. Download OpenD: https://www.futunn.com/download/OpenD")
        print("   2. Start: OpenD --ip 127.0.0.1 --port 11111")
        print("   3. Scan QR code with Futu app to authorize")

except Exception as e:
    print(f"   [ERROR] {e}")
    print("\n   OpenD not running. Start it with:")
    print("   OpenD --ip 127.0.0.1 --port 11111")
