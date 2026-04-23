#!/usr/bin/env python3
"""
测试所有实时行情 API
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from m9_paper_trader.alltick_feed import AllTickFeed
from m9_paper_trader.itick_feed import ITickFeed
from m9_paper_trader.price_feed import AKShareRealtimeFeed, make_price_feed

# API Keys
ALLTICK_KEY = "1230baa6b4df511826b43549873eecfa-c-app"
ITICK_KEY = "3f9318ac81e449bcb3ccfcf05aaf54910d89268520354dccba95c1c272cd06d6"

# 测试股票
TEST_SYMBOLS = [
    "600519.SH",  # 贵州茅台
    "000858.SZ",  # 五粮液
    "0700.HK",    # 腾讯控股
    "AAPL.US",    # 苹果
]


def test_single_feed(feed, name):
    """测试单个数据源"""
    print(f"\n{'='*60}")
    print(f"测试 {name}")
    print('='*60)
    
    for symbol in TEST_SYMBOLS:
        try:
            price = feed.get_price(symbol)
            if price:
                print(f"✅ {symbol:12} | 价格: {price.price:8.2f} | 涨跌: {price.change_pct:+6.2f}% | 来源: {price.source}")
            else:
                print(f"❌ {symbol:12} | 无数据")
        except Exception as e:
            print(f"❌ {symbol:12} | 错误: {e}")


def test_composite():
    """测试组合数据源（自动 fallback）"""
    print(f"\n{'='*60}")
    print("测试 CompositeFeed（自动 fallback）")
    print('='*60)
    
    feed = make_price_feed(
        mode="composite",
        alltick_key=ALLTICK_KEY,
        itick_key=ITICK_KEY,
    )
    
    for symbol in TEST_SYMBOLS:
        try:
            price = feed.get_price(symbol)
            if price:
                print(f"✅ {symbol:12} | 价格: {price.price:8.2f} | 涨跌: {price.change_pct:+6.2f}% | 来源: {price.source}")
            else:
                print(f"❌ {symbol:12} | 无数据")
        except Exception as e:
            print(f"❌ {symbol:12} | 错误: {e}")


if __name__ == "__main__":
    print("🚀 开始测试实时行情 API")
    print(f"测试时间: {__import__('datetime').datetime.now()}")
    
    # 测试各个数据源
    test_single_feed(ITickFeed(ITICK_KEY), "iTick（实时）")
    test_single_feed(AllTickFeed(ALLTICK_KEY), "AllTick（实时）")
    test_single_feed(AKShareRealtimeFeed(), "AKShare（3-5分钟延迟）")
    
    # 测试组合数据源
    test_composite()
    
    print("\n✅ 测试完成")
