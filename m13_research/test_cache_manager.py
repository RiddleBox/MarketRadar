"""
M13 Cache Manager 单元测试
"""

import unittest
from pathlib import Path
import tempfile
import shutil
import sys
import io
from datetime import datetime, timedelta

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from m13_research.cache_manager import CacheManager
from core.schemas import ResearchReport, ResearchLevel, ResearchTrigger


class TestCacheManager(unittest.TestCase):
    """测试CacheManager功能"""

    def setUp(self):
        """测试前准备"""
        # 创建临时缓存目录
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir)
        self.cache_manager = CacheManager(self.cache_dir)

    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        shutil.rmtree(self.temp_dir)

    def test_cache_directory_creation(self):
        """测试缓存目录自动创建"""
        # 验证目录已创建
        self.assertTrue(self.cache_dir.exists())
        self.assertTrue(self.cache_dir.is_dir())

    def test_save_and_get_research(self):
        """测试保存和获取调研报告"""
        # 创建测试报告
        report = ResearchReport(
            symbol="600000.SH",
            research_level=ResearchLevel.QUICK,
            triggered_by=ResearchTrigger.M1_5,
            summary="测试报告",
            confidence_multiplier=1.2
        )

        # 保存报告
        self.cache_manager.save_research(report)

        # 获取报告
        cached_report = self.cache_manager.get_cached_research(
            symbol="600000.SH",
            level=ResearchLevel.QUICK
        )

        # 验证报告内容
        self.assertIsNotNone(cached_report)
        self.assertEqual(cached_report.symbol, "600000.SH")
        self.assertEqual(cached_report.summary, "测试报告")
        self.assertEqual(cached_report.confidence_multiplier, 1.2)

    def test_cache_miss(self):
        """测试缓存未命中"""
        # 获取不存在的报告
        cached_report = self.cache_manager.get_cached_research(
            symbol="999999.SH",
            level=ResearchLevel.QUICK
        )

        # 验证返回None
        self.assertIsNone(cached_report)

    def test_cache_expiration_quick(self):
        """测试快速调研缓存过期（6小时）"""
        # 创建测试报告
        report = ResearchReport(
            symbol="600000.SH",
            research_level=ResearchLevel.QUICK,
            triggered_by=ResearchTrigger.M1_5,
            summary="测试报告"
        )

        # 保存报告
        self.cache_manager.save_research(report)

        # 修改缓存文件时间为7小时前
        cache_key = self.cache_manager._get_cache_key("600000.SH", ResearchLevel.QUICK)
        cache_file = self.cache_dir / f"{cache_key}.json"
        old_time = datetime.now().timestamp() - (7 * 3600)
        cache_file.touch()
        import os
        os.utime(cache_file, (old_time, old_time))

        # 获取报告（应该过期）
        cached_report = self.cache_manager.get_cached_research(
            symbol="600000.SH",
            level=ResearchLevel.QUICK
        )

        # 验证返回None（已过期）
        self.assertIsNone(cached_report)

    def test_cache_expiration_standard(self):
        """测试标准调研缓存过期（12小时）"""
        # 创建测试报告
        report = ResearchReport(
            symbol="600000.SH",
            research_level=ResearchLevel.STANDARD,
            triggered_by=ResearchTrigger.M12,
            summary="测试报告"
        )

        # 保存报告
        self.cache_manager.save_research(report)

        # 修改缓存文件时间为13小时前
        cache_key = self.cache_manager._get_cache_key("600000.SH", ResearchLevel.STANDARD)
        cache_file = self.cache_dir / f"{cache_key}.json"
        old_time = datetime.now().timestamp() - (13 * 3600)
        cache_file.touch()
        import os
        os.utime(cache_file, (old_time, old_time))

        # 获取报告（应该过期）
        cached_report = self.cache_manager.get_cached_research(
            symbol="600000.SH",
            level=ResearchLevel.STANDARD
        )

        # 验证返回None（已过期）
        self.assertIsNone(cached_report)

    def test_cache_expiration_deep(self):
        """测试深度调研缓存过期（24小时）"""
        # 创建测试报告
        report = ResearchReport(
            symbol="600000.SH",
            research_level=ResearchLevel.DEEP,
            triggered_by=ResearchTrigger.M3,
            summary="测试报告"
        )

        # 保存报告
        self.cache_manager.save_research(report)

        # 修改缓存文件时间为25小时前
        cache_key = self.cache_manager._get_cache_key("600000.SH", ResearchLevel.DEEP)
        cache_file = self.cache_dir / f"{cache_key}.json"
        old_time = datetime.now().timestamp() - (25 * 3600)
        cache_file.touch()
        import os
        os.utime(cache_file, (old_time, old_time))

        # 获取报告（应该过期）
        cached_report = self.cache_manager.get_cached_research(
            symbol="600000.SH",
            level=ResearchLevel.DEEP
        )

        # 验证返回None（已过期）
        self.assertIsNone(cached_report)

    def test_cache_key_generation(self):
        """测试缓存键生成"""
        # 测试不同Level生成不同的键
        key_quick = self.cache_manager._get_cache_key("600000.SH", ResearchLevel.QUICK)
        key_standard = self.cache_manager._get_cache_key("600000.SH", ResearchLevel.STANDARD)
        key_deep = self.cache_manager._get_cache_key("600000.SH", ResearchLevel.DEEP)

        # 验证键不同
        self.assertNotEqual(key_quick, key_standard)
        self.assertNotEqual(key_standard, key_deep)
        self.assertNotEqual(key_quick, key_deep)

        # 验证键包含日期
        today = datetime.now().strftime("%Y%m%d")
        self.assertIn(today, key_quick)
        self.assertIn(today, key_standard)
        self.assertIn(today, key_deep)

    def test_multiple_symbols_cache(self):
        """测试多个标的的缓存"""
        symbols = ["600000.SH", "000001.SZ", "600036.SH"]

        # 保存多个报告
        for symbol in symbols:
            report = ResearchReport(
                symbol=symbol,
                research_level=ResearchLevel.QUICK,
                triggered_by=ResearchTrigger.M1_5,
                summary=f"{symbol}的报告"
            )
            self.cache_manager.save_research(report)

        # 验证都能获取
        for symbol in symbols:
            cached_report = self.cache_manager.get_cached_research(
                symbol=symbol,
                level=ResearchLevel.QUICK
            )
            self.assertIsNotNone(cached_report)
            self.assertEqual(cached_report.symbol, symbol)

    def test_cache_statistics(self):
        """测试缓存统计"""
        # 保存几个报告
        for i in range(5):
            report = ResearchReport(
                symbol=f"60000{i}.SH",
                research_level=ResearchLevel.QUICK,
                triggered_by=ResearchTrigger.M1_5,
                summary=f"报告{i}"
            )
            self.cache_manager.save_research(report)

        # 获取统计
        stats = self.cache_manager.get_cache_stats()

        # 验证统计信息
        self.assertIn("total_cached", stats)
        self.assertIn("by_level", stats)
        self.assertEqual(stats["total_cached"], 5)
        self.assertEqual(stats["by_level"]["QUICK"], 5)

    def test_clear_expired_cache(self):
        """测试清理过期缓存"""
        # 保存一个新报告
        report_new = ResearchReport(
            symbol="600000.SH",
            research_level=ResearchLevel.QUICK,
            triggered_by=ResearchTrigger.M1_5,
            summary="新报告"
        )
        self.cache_manager.save_research(report_new)

        # 保存一个旧报告
        report_old = ResearchReport(
            symbol="600001.SH",
            research_level=ResearchLevel.QUICK,
            triggered_by=ResearchTrigger.M1_5,
            summary="旧报告"
        )
        self.cache_manager.save_research(report_old)

        # 修改旧报告时间为7小时前
        cache_key = self.cache_manager._get_cache_key("600001.SH", ResearchLevel.QUICK)
        cache_file = self.cache_dir / f"{cache_key}.json"
        old_time = datetime.now().timestamp() - (7 * 3600)
        import os
        os.utime(cache_file, (old_time, old_time))

        # 清理过期缓存
        cleared = self.cache_manager.clear_expired_cache()

        # 验证清理了1个
        self.assertEqual(cleared, 1)

        # 验证新报告还在
        cached_new = self.cache_manager.get_cached_research("600000.SH", ResearchLevel.QUICK)
        self.assertIsNotNone(cached_new)

        # 验证旧报告已删除
        cached_old = self.cache_manager.get_cached_research("600001.SH", ResearchLevel.QUICK)
        self.assertIsNone(cached_old)

    def test_clear_all_cache(self):
        """测试清空所有缓存"""
        # 保存多个报告
        for i in range(3):
            report = ResearchReport(
                symbol=f"60000{i}.SH",
                research_level=ResearchLevel.QUICK,
                triggered_by=ResearchTrigger.M1_5,
                summary=f"报告{i}"
            )
            self.cache_manager.save_research(report)

        # 清空所有缓存
        cleared = self.cache_manager.clear_all_cache()

        # 验证清理了3个
        self.assertEqual(cleared, 3)

        # 验证所有报告都不存在
        for i in range(3):
            cached = self.cache_manager.get_cached_research(
                f"60000{i}.SH",
                ResearchLevel.QUICK
            )
            self.assertIsNone(cached)

    def test_cache_with_complex_data(self):
        """测试缓存复杂数据"""
        # 创建包含复杂数据的报告
        report = ResearchReport(
            symbol="600000.SH",
            research_level=ResearchLevel.DEEP,
            triggered_by=ResearchTrigger.M3,
            reports=[
                {"title": "研报1", "summary": "摘要1"},
                {"title": "研报2", "summary": "摘要2"}
            ],
            news=[
                {"title": "新闻1", "content": "内容1"},
                {"title": "新闻2", "content": "内容2"}
            ],
            fundamentals={
                "roe": 0.12,
                "pe": 5.5,
                "pb": 0.8
            },
            summary="深度分析报告",
            key_findings=["发现1", "发现2", "发现3"],
            confidence_delta=0.15,
            has_major_negative=False
        )

        # 保存报告
        self.cache_manager.save_research(report)

        # 获取报告
        cached_report = self.cache_manager.get_cached_research(
            symbol="600000.SH",
            level=ResearchLevel.DEEP
        )

        # 验证所有数据都正确
        self.assertEqual(len(cached_report.reports), 2)
        self.assertEqual(len(cached_report.news), 2)
        self.assertEqual(len(cached_report.key_findings), 3)
        self.assertEqual(cached_report.fundamentals["roe"], 0.12)
        self.assertEqual(cached_report.confidence_delta, 0.15)

    def test_cache_file_corruption(self):
        """测试缓存文件损坏的处理"""
        # 创建一个损坏的缓存文件
        cache_key = self.cache_manager._get_cache_key("600000.SH", ResearchLevel.QUICK)
        cache_file = self.cache_dir / f"{cache_key}.json"
        cache_file.write_text("这不是有效的JSON")

        # 尝试获取（应该返回None）
        cached_report = self.cache_manager.get_cached_research(
            symbol="600000.SH",
            level=ResearchLevel.QUICK
        )

        # 验证返回None
        self.assertIsNone(cached_report)


if __name__ == '__main__':
    unittest.main(verbosity=2)
