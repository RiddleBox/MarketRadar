"""
tests/test_m0.py — M0 收集器测试

覆盖：
  1. ManualProvider 文本导入
  2. Normalizer 标准化
  3. 去重逻辑
"""
import tempfile
from pathlib import Path
from datetime import datetime

from m0_collector.providers.manual import ManualProvider
from m0_collector.normalizer import Normalizer
from m0_collector.dedup import DedupIndex


class TestManualProvider:
    def test_basic_fetch(self):
        provider = ManualProvider(source_name="测试来源")
        items = provider.fetch(
            text="【财联社讯】中国人民银行今日宣布，将7天期逆回购操作利率下调25bp",
            title="央行超预期降息25bp",
            source_url="https://test.example.com/article/001",
            published_at="2026-04-13 10:00:00",
        )
        assert len(items) >= 1
        assert items[0].title == "央行超预期降息25bp"


class TestNormalizer:
    def test_normalize(self):
        from m0_collector.dedup import DedupIndex
        from m0_collector.models import RawArticle
        dedup = DedupIndex()
        normalizer = Normalizer(dedup_index=dedup)
        article = RawArticle(
            title="央行超预期降息25bp",
            content="【财联社讯】中国人民银行今日宣布，将7天期逆回购操作利率下调25bp",
            raw_published_at="2026-04-13 10:00:00",
            source_name="测试来源",
            source_url="https://test.example.com/001",
            provider_id="manual",
            language="zh",
        )
        items, skipped, errors = normalizer.normalize([article])
        assert len(items) >= 1
        assert skipped == 0

        items2, skipped2, _ = normalizer.normalize([article])
        assert skipped2 == 1


class TestDedupIndex:
    def test_url_dedup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            idx = DedupIndex(index_path=Path(tmpdir) / "dedup.json")
            url = "https://test.example.com/article/001"
            content = "测试内容abc"
            assert not idx.is_duplicate(url, content)
            idx.add(url, content)
            idx.save()
            assert idx.is_duplicate(url, content)
