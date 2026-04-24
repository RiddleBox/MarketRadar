#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试多数据源集成到日常流程
"""
import sys
import os

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 设置环境变量
os.environ['NEWSAPI_KEY'] = '6wB0t_ne7CjozVmoTWP_LZlcGxpqsvDB'
os.environ['FINNHUB_API_KEY'] = 'd7lhlbhr01qm7o0bsj30d7lhlbhr01qm7o0bsj3g'

from core.schemas import Market
from m0_collector.providers.akshare_news import AkshareNewsProvider
from m0_collector.providers.finnhub_provider import FinnhubProvider

print("=" * 60)
print("测试多数据源集成")
print("=" * 60)

# 测试1: A股数据源 (AKShare)
print("\n[1/3] 测试 A股数据源 (AKShare)")
try:
    akshare = AkshareNewsProvider()
    if akshare.is_available():
        articles = akshare.fetch(limit=5)
        print(f"  ✓ AKShare: 获取 {len(articles)} 条A股新闻")
        if articles:
            print(f"  示例: {articles[0].title[:50]}...")
    else:
        print("  ✗ AKShare 不可用")
except Exception as e:
    print(f"  ✗ AKShare 失败: {e}")

# 测试2: 港股数据源 (Finnhub)
print("\n[2/3] 测试 港股数据源 (Finnhub)")
try:
    finnhub = FinnhubProvider()
    articles = finnhub.fetch(category="general")
    print(f"  ✓ Finnhub: 获取 {len(articles)} 条市场新闻")
    if articles:
        print(f"  示例: {articles[0].title[:50]}...")
except Exception as e:
    print(f"  ✗ Finnhub 失败: {e}")

# 测试3: 美股数据源 (Finnhub)
print("\n[3/3] 测试 美股数据源 (Finnhub)")
try:
    finnhub = FinnhubProvider()
    articles = finnhub.fetch_company_news(symbol="AAPL")
    print(f"  ✓ Finnhub: 获取 {len(articles)} 条AAPL新闻")
    if articles:
        print(f"  示例: {articles[0].title[:50]}...")
except Exception as e:
    print(f"  ✗ Finnhub 失败: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
print("\n下一步: 运行完整流程")
print("  python run_daily_pipeline.py --mode premarket --market A_SHARE,HK,US --limit 5")
