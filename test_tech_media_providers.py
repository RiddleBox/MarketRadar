"""
测试科技媒体Provider
"""

import sys
sys.path.insert(0, '.')

from m0_collector.providers.tech_media_provider import Kr36Provider, HuxiuProvider


def test_36kr_provider():
    """测试36氪Provider"""
    print("=" * 60)
    print("测试36氪Provider")
    print("=" * 60)

    provider = Kr36Provider()

    categories = ["tech", "latest"]

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


def test_huxiu_provider():
    """测试虎嗅Provider"""
    print("\n" + "=" * 60)
    print("测试虎嗅Provider")
    print("=" * 60)

    provider = HuxiuProvider()

    categories = ["tech", "finance"]

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


if __name__ == "__main__":
    test_36kr_provider()
    test_huxiu_provider()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
