"""
测试国际新闻源 (NewsAPI + Finnhub)
"""
import os
import sys

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from m0_collector.providers.newsapi_provider import NewsAPIProvider
from m0_collector.providers.finnhub_provider import FinnhubProvider

def test_newsapi():
    """测试 NewsAPI"""
    print("\n=== 测试 NewsAPI ===")

    # 需要设置环境变量 NEWSAPI_KEY
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        print("⚠️  未设置 NEWSAPI_KEY 环境变量")
        return

    provider = NewsAPIProvider(api_key=api_key)

    # 测试1: 搜索港股相关新闻
    print("\n1. 搜索港股新闻 (HSBC, Tencent):")
    articles = provider.fetch(query="HSBC OR Tencent", language="en", page_size=5)
    print(f"   获取到 {len(articles)} 篇文章")
    for i, article in enumerate(articles[:3], 1):
        print(f"   [{i}] {article.title[:60]}...")
        print(f"       来源: {article.source_name} | 时间: {article.raw_published_at}")

    # 测试2: 搜索美股相关新闻
    print("\n2. 搜索美股新闻 (Apple, Tesla):")
    articles = provider.fetch(query="Apple OR Tesla", language="en", page_size=5)
    print(f"   获取到 {len(articles)} 篇文章")
    for i, article in enumerate(articles[:3], 1):
        print(f"   [{i}] {article.title[:60]}...")
        print(f"       来源: {article.source_name} | 时间: {article.raw_published_at}")

def test_finnhub():
    """测试 Finnhub"""
    print("\n=== 测试 Finnhub ===")

    # 需要设置环境变量 FINNHUB_API_KEY
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        print("⚠️  未设置 FINNHUB_API_KEY 环境变量")
        return

    provider = FinnhubProvider(api_key=api_key)

    # 测试1: 获取港股新闻 (腾讯)
    print("\n1. 腾讯控股 (0700.HK) 新闻:")
    articles = provider.fetch_company_news(symbol="0700.HK")
    print(f"   获取到 {len(articles)} 篇文章")
    for i, article in enumerate(articles[:3], 1):
        print(f"   [{i}] {article.title[:60]}...")
        print(f"       来源: {article.source_name} | 时间: {article.raw_published_at}")

    # 测试2: 获取美股新闻 (苹果)
    print("\n2. 苹果 (AAPL) 新闻:")
    articles = provider.fetch_company_news(symbol="AAPL")
    print(f"   获取到 {len(articles)} 篇文章")
    for i, article in enumerate(articles[:3], 1):
        print(f"   [{i}] {article.title[:60]}...")
        print(f"       来源: {article.source_name} | 时间: {article.raw_published_at}")

    # 测试3: 获取市场新闻
    print("\n3. 市场新闻 (general):")
    articles = provider.fetch_market_news(category="general")
    print(f"   获取到 {len(articles)} 篇文章")
    for i, article in enumerate(articles[:3], 1):
        print(f"   [{i}] {article.title[:60]}...")
        print(f"       来源: {article.source_name} | 时间: {article.raw_published_at}")

if __name__ == "__main__":
    print("=" * 60)
    print("国际新闻源测试")
    print("=" * 60)

    test_newsapi()
    test_finnhub()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
