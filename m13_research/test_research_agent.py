"""
M13 Research Agent 单元测试
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
import io

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from m13_research.research_agent import ResearchAgent
from m13_research.llm_analyzer import LLMAnalyzer
from m13_research.cache_manager import CacheManager
from core.schemas import ResearchLevel, ResearchTrigger, ResearchReport


class TestResearchAgent(unittest.TestCase):
    """测试ResearchAgent核心功能"""

    def setUp(self):
        """测试前准备"""
        # Mock依赖
        self.mock_data_manager = Mock()
        self.mock_llm_analyzer = Mock()
        self.mock_cache_manager = Mock()

        # 创建ResearchAgent实例
        self.agent = ResearchAgent(
            data_manager=self.mock_data_manager,
            llm_analyzer=self.mock_llm_analyzer,
            cache_manager=self.mock_cache_manager,
            max_concurrent=5
        )

    def test_quick_research_basic(self):
        """测试快速调研基本流程"""
        # 准备测试数据
        symbol = "600000.SH"
        context = "降息利好银行股"

        # Mock缓存未命中
        self.mock_cache_manager.get_cached_research.return_value = None

        # Mock数据收集
        self.mock_data_manager.search_research_reports.return_value = [
            {"title": "平安银行：零售转型成效显著", "date": "2026-05-01"}
        ]
        self.mock_data_manager.get_latest_fundamentals.return_value = {
            "roe": 0.12,
            "pe": 5.5
        }

        # Mock LLM分析
        self.mock_llm_analyzer.quick_verify.return_value = {
            "summary": "基本面良好",
            "confidence_multiplier": 1.2,
            "has_major_negative": False
        }

        # 执行调研
        result = self.agent.quick_research(symbol, context)

        # 验证结果
        self.assertIsInstance(result, ResearchReport)
        self.assertEqual(result.symbol, symbol)
        self.assertEqual(result.research_level, ResearchLevel.QUICK)
        self.assertEqual(result.triggered_by, ResearchTrigger.M1_5)
        self.assertGreater(result.confidence_multiplier, 1.0)
        self.assertFalse(result.has_major_negative)

        # 验证缓存写入
        self.mock_cache_manager.save_research.assert_called_once()

    def test_quick_research_with_cache(self):
        """测试快速调研缓存命中"""
        symbol = "600000.SH"
        context = "降息利好银行股"

        # Mock缓存命中
        cached_report = ResearchReport(
            symbol=symbol,
            research_level=ResearchLevel.QUICK,
            triggered_by=ResearchTrigger.M1_5,
            summary="缓存的调研报告",
            confidence_multiplier=1.1
        )
        self.mock_cache_manager.get_cached_research.return_value = cached_report

        # 执行调研
        result = self.agent.quick_research(symbol, context)

        # 验证返回缓存结果
        self.assertEqual(result, cached_report)

        # 验证没有调用数据收集
        self.mock_data_manager.search_research_reports.assert_not_called()
        self.mock_llm_analyzer.quick_verify.assert_not_called()

    def test_standard_research_basic(self):
        """测试标准调研基本流程"""
        symbol = "600000.SH"
        context = "价格异动+5.2%"

        # Mock缓存未命中
        self.mock_cache_manager.get_cached_research.return_value = None

        # Mock数据收集
        self.mock_data_manager.search_research_reports.return_value = [
            {"title": "研报1", "date": "2026-05-01"},
            {"title": "研报2", "date": "2026-05-02"}
        ]
        self.mock_data_manager.search_news.return_value = [
            {"title": "新闻1", "date": "2026-05-03"}
        ]
        self.mock_data_manager.get_latest_fundamentals.return_value = {
            "roe": 0.12
        }

        # Mock LLM分析
        self.mock_llm_analyzer.standard_analyze.return_value = {
            "summary": "业绩超预期",
            "key_findings": ["营收增长30%", "净利润翻倍"],
            "confidence_delta": 0.2,
            "has_major_negative": False
        }

        # 执行调研
        result = self.agent.standard_research(symbol, context)

        # 验证结果
        self.assertEqual(result.research_level, ResearchLevel.STANDARD)
        self.assertEqual(result.triggered_by, ResearchTrigger.M12)
        self.assertGreater(len(result.reports), 0)
        self.assertGreater(len(result.news), 0)
        self.assertGreater(result.confidence_delta, 0)

    def test_deep_research_basic(self):
        """测试深度调研基本流程"""
        symbol = "600000.SH"
        context = "机会判断：零售转型带来估值重估"

        # Mock缓存未命中
        self.mock_cache_manager.get_cached_research.return_value = None

        # Mock数据收集
        self.mock_data_manager.search_research_reports.return_value = [
            {"title": f"研报{i}", "date": "2026-05-01"} for i in range(5)
        ]
        self.mock_data_manager.search_news.return_value = [
            {"title": f"新闻{i}", "date": "2026-05-01"} for i in range(10)
        ]
        self.mock_data_manager.get_latest_fundamentals.return_value = {
            "roe": 0.12,
            "pe": 5.5,
            "pb": 0.8
        }
        self.mock_data_manager.semantic_search.return_value = [
            {"content": "行业趋势分析"}
        ]

        # Mock LLM分析
        self.mock_llm_analyzer.deep_analyze.return_value = {
            "summary": "深度分析报告",
            "key_findings": ["发现1", "发现2", "发现3"],
            "confidence_delta": 0.15,
            "has_major_negative": False
        }

        # 执行调研
        result = self.agent.deep_research(symbol, context)

        # 验证结果
        self.assertEqual(result.research_level, ResearchLevel.DEEP)
        self.assertEqual(result.triggered_by, ResearchTrigger.M3)
        self.assertGreater(len(result.reports), 0)
        self.assertGreater(len(result.news), 0)
        self.assertGreater(len(result.key_findings), 0)

    def test_research_with_major_negative(self):
        """测试发现重大利空的情况"""
        symbol = "600000.SH"
        context = "降息利好银行股"

        # Mock缓存未命中
        self.mock_cache_manager.get_cached_research.return_value = None

        # Mock数据收集
        self.mock_data_manager.search_research_reports.return_value = [
            {"title": "平安银行：不良率飙升", "date": "2026-05-01"}
        ]
        self.mock_data_manager.get_latest_fundamentals.return_value = {
            "roe": 0.05,  # 低ROE
            "npl_ratio": 0.05  # 高不良率
        }

        # Mock LLM分析 - 发现重大利空
        self.mock_llm_analyzer.quick_verify.return_value = {
            "summary": "不良率飙升，资产质量恶化",
            "confidence_multiplier": 0.6,
            "has_major_negative": True
        }

        # 执行调研
        result = self.agent.quick_research(symbol, context)

        # 验证结果
        self.assertTrue(result.has_major_negative)
        self.assertLess(result.confidence_multiplier, 1.0)

    def test_research_timeout(self):
        """测试调研超时处理"""
        symbol = "600000.SH"
        context = "测试超时"

        # Mock缓存未命中
        self.mock_cache_manager.get_cached_research.return_value = None

        # Mock数据收集超时
        def slow_search(*args, **kwargs):
            import time
            time.sleep(5)  # 超过30秒超时
            return []

        self.mock_data_manager.search_research_reports.side_effect = slow_search

        # 执行调研（应该超时返回部分结果）
        result = self.agent.quick_research(symbol, context)

        # 验证返回了结果（即使超时）
        self.assertIsInstance(result, ResearchReport)
        self.assertEqual(result.symbol, symbol)

    def test_research_data_source_failure(self):
        """测试数据源失败的容错处理"""
        symbol = "600000.SH"
        context = "测试容错"

        # Mock缓存未命中
        self.mock_cache_manager.get_cached_research.return_value = None

        # Mock数据源失败
        self.mock_data_manager.search_research_reports.side_effect = Exception("数据源失败")
        self.mock_data_manager.search_news.return_value = [
            {"title": "新闻1", "date": "2026-05-01"}
        ]
        self.mock_data_manager.get_latest_fundamentals.return_value = {}

        # Mock LLM分析
        self.mock_llm_analyzer.standard_analyze.return_value = {
            "summary": "基于有限信息的分析",
            "key_findings": ["信息不足"],
            "confidence_delta": 0.0,
            "has_major_negative": False
        }

        # 执行调研（应该继续，使用其他数据源）
        result = self.agent.standard_research(symbol, context)

        # 验证返回了结果
        self.assertIsInstance(result, ResearchReport)
        self.assertEqual(len(result.reports), 0)  # 研报收集失败
        self.assertGreater(len(result.news), 0)  # 新闻收集成功

    def test_concurrent_research(self):
        """测试并发调研控制"""
        symbols = [f"60000{i}.SH" for i in range(10)]
        context = "批量调研"

        # Mock缓存未命中
        self.mock_cache_manager.get_cached_research.return_value = None

        # Mock数据收集
        self.mock_data_manager.search_research_reports.return_value = []
        self.mock_data_manager.get_latest_fundamentals.return_value = {}
        self.mock_llm_analyzer.quick_verify.return_value = {
            "summary": "测试",
            "confidence_multiplier": 1.0,
            "has_major_negative": False
        }

        # 执行并发调研
        results = []
        for symbol in symbols:
            result = self.agent.quick_research(symbol, context)
            results.append(result)

        # 验证所有调研都完成
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertIsInstance(result, ResearchReport)


class TestResearchAgentIntegration(unittest.TestCase):
    """测试ResearchAgent集成功能（需要真实依赖）"""

    @unittest.skip("需要真实数据提供者")
    def test_real_quick_research(self):
        """测试真实快速调研（集成测试）"""
        from integrations.data_provider_manager import get_global_data_manager
        from integrations.init_data_providers import initialize_data_providers
        from core.llm_client import LLMClient

        # 初始化真实依赖
        initialize_data_providers()
        data_manager = get_global_data_manager()
        llm_client = LLMClient()
        llm_analyzer = LLMAnalyzer(llm_client)
        cache_manager = CacheManager(Path("data/m13_cache_test"))

        # 创建真实agent
        agent = ResearchAgent(
            data_manager=data_manager,
            llm_analyzer=llm_analyzer,
            cache_manager=cache_manager
        )

        # 执行真实调研
        result = agent.quick_research(
            symbol="600000.SH",
            context="测试真实调研"
        )

        # 验证结果
        self.assertIsInstance(result, ResearchReport)
        self.assertEqual(result.symbol, "600000.SH")
        print(f"\n调研结果: {result.summary}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
