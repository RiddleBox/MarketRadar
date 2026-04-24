"""
测试新华社Provider
"""

import sys
from m0_collector.providers.xinhua_provider import XinhuaProvider


def test_xinhua_provider():
    """测试新华社新闻采集"""
    print("=" * 60)
    print("测试新华社Provider")
    print("=" * 60)

    provider = XinhuaProvider()

    # 测试各个类别
    categories = ["politics", "world", "finance", "tech"]

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
                    if article.content:
                        preview = article.content[:100].replace('\n', ' ')
                        print(f"   内容: {preview}...")
            else:
                print("未获取到新闻")

        except Exception as e:
            print(f"错误: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_xinhua_provider()
