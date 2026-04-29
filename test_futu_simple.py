#!/usr/bin/env python3
"""Simple Futu OpenD connection test"""

from futu import OpenQuoteContext, RET_OK

print("Connecting to OpenD at 127.0.0.1:11111...")
quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

print("Testing AAPL.US market snapshot...")
ret, data = quote_ctx.get_market_snapshot(['US.AAPL'])

if ret == RET_OK:
    print(f"\n[SUCCESS] Got data:")
    row = data.iloc[0]
    print(f"  Code: {row['code']}")
    print(f"  Name: {row['name']}")
    print(f"  Last Price: ${row['last_price']:.2f}")
    print(f"  Prev Close: ${row['prev_close_price']:.2f}")
    print(f"  Change: ${row['last_price'] - row['prev_close_price']:.2f}")
    print(f"  Change %: {((row['last_price'] - row['prev_close_price']) / row['prev_close_price'] * 100):.2f}%")
    print(f"  Volume: {row['volume']:,.0f}")
    print(f"  Update Time: {row['update_time']}")
else:
    print(f"\n[FAIL] Error: {data}")

quote_ctx.close()
print("\nConnection closed.")
