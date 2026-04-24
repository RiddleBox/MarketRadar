"""
测试发改委和外交部Provider
"""

import sys
sys.path.insert(0, '.')

from m0_collector.providers.ndrc_provider import NDRCProvider
from m0_collector.providers.fmprc_provider import FMPRCProvider


def test_ndrc_provider():
    """测试发改委Provider"""
    print("=" * 60)
    print("测试发改委Provider")
    print("=" * 60)

    provider = NDRCProvider()

    categories = ["policy", "planning", "investment", "industry"]

    for category in categories:
        print(f"\n[{category.upper()}] 测试...")
        try:
            articles = provider.fetch(category=category, limit=5)
            print(f"成功获取 {len(articles)} 篇新闻")

            if articles:
                print("\n示例新闻:")
                for i, article in enumerate(articles[:2], 1):
                    print(f"\n{i}. {article.title}")
                    print(f"   来源: {article.source_name}")
                    print(f"   时间: {article.raw_published_at}")
                    print(f"   链接: {article.source_url}")
            else:
                print("未获取到新闻")

        except Exception as e:
            print(f"错误: {e}")


def test_fmprc_provider():
    """测试外交部Provider"""
    print("\n" + "=" * 60)
    print("测试外交部Provider")
    print("=" * 60)

    provider = FMPRCProvider()

    categories = ["news", "spokesperson"]

    for category in categories:
        print(f"\n[{category.upper()}] 测试...")
        try:
            articles = provider.fetch(category=category, limit=5)
            print(f"成功获取 {len(articles)} 篇新闻")

            if articles:
                print("\n示例新闻:")
                for i, article in enumerate(articles[:2], 1):
                    print(f"\n{i}. {article.title}")
                    print(f"   来源: {article.source_name}")
                    print(f"   时间: {article.raw_published_at}")
                    print(f"   链接: {article.source_url}")
            else:
                print("未获取到新闻")

        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    test_ndrc_provider()
    test_fmprc_provider()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
