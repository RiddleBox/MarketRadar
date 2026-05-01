"""
测试 NewsDeduplicator 去重功能
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from m0_collector.deduplicator import NewsDeduplicator


def test_deduplicator():
    """测试去重器"""
    print("=" * 60)
    print("测试 NewsDeduplicator 去重功能")
    print("=" * 60)

    # 初始化去重器（使用测试数据库）
    dedup = NewsDeduplicator(db_path="data/test_news_dedup.db")

    # 测试1: URL精确匹配
    print("\n[测试1] URL精确匹配去重")
    news1 = {
        "url": "https://example.com/news/123",
        "title": "国家发改委发布新政策",
        "source": "新华社"
    }

    print(f"  第1次插入: {news1['title']}")
    is_dup = dedup.is_duplicate(news1['url'], news1['title'], news1['source'])
    print(f"    是否重复: {is_dup}")
    assert not is_dup, "第1次应该不重复"

    dedup.mark_processed(news1['url'], news1['title'], news1['source'])
    print(f"    已标记为已处理")

    print(f"  第2次插入: {news1['title']}")
    is_dup = dedup.is_duplicate(news1['url'], news1['title'], news1['source'])
    print(f"    是否重复: {is_dup}")
    assert is_dup, "第2次应该重复（URL相同）"

    # 测试2: 标题相似度去重
    print("\n[测试2] 标题相似度去重")
    news2 = {
        "url": "https://example.com/news/456",  # 不同URL
        "title": "国家发改委 发布 新政策！",  # 相似标题（不同标点、空格）
        "source": "人民日报"
    }

    print(f"  插入相似标题: {news2['title']}")
    is_dup = dedup.is_duplicate(news2['url'], news2['title'], news2['source'])
    print(f"    是否重复: {is_dup}")
    assert is_dup, "应该重复（标题相似）"

    # 测试3: 完全不同的新闻
    print("\n[测试3] 完全不同的新闻")
    news3 = {
        "url": "https://example.com/news/789",
        "title": "科技公司发布新产品",
        "source": "36氪"
    }

    print(f"  插入新新闻: {news3['title']}")
    is_dup = dedup.is_duplicate(news3['url'], news3['title'], news3['source'])
    print(f"    是否重复: {is_dup}")
    assert not is_dup, "应该不重复（全新新闻）"

    dedup.mark_processed(news3['url'], news3['title'], news3['source'])

    # 测试4: 统计信息
    print("\n[测试4] 统计信息")
    stats = dedup.get_stats()
    print(f"  总处理数: {stats['total_processed']}")
    print(f"  按来源统计: {stats['by_source']}")
    assert stats['total_processed'] == 2, "应该有2条记录"

    print("\n" + "=" * 60)
    print("✅ 所有测试通过")
    print("=" * 60)


if __name__ == "__main__":
    test_deduplicator()
