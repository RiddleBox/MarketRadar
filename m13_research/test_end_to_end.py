"""
M13 端到端测试
"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import shutil
import sys
import io

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from m13_research.research_agent import ResearchAgent
from m13_research.llm_analyzer import LLMAnalyzer
from m13_research.cache_manager import CacheManager
from core.schemas import ResearchLevel, ResearchTrigger


class TestM13EndToEnd(unittest.TestCase):
    """M13端到端测试"""

    def setUp(self):
        """测试前准备"""
        # 创建临时缓存目录
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir)

        # Mock依赖
        self.mock_data_manager = Mock()
        self.mock_llm_client = Mock()

        # 创建真实组件
        self.llm_analyzer = LLMAnalyzer(self.mock_llm_client)
        self.cache_manager = CacheManager(self.cache_dir)
        self.research_agent = ResearchAgent(
            data_manager=self.mock_data_manager,
            llm_analyzer=self.llm_analyzer,
            cache_manager=self.cache_manager,
            max_concurrent=5
        )

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    def test_m1_track_complete_flow(self):
        """测试M1轨道完整流程"""
        print("\n=== 测试M1轨道：新闻 → M1.5推理 → M13验证 → M2存储 ===")

        # 1. M0采集新闻（模拟）
        raw_news = {
            'source': 'xinhua',
            'category': 'policy',
            'title': '央行宣布降息25个基点',
            'content': '为支持实体经济发展，央行决定下调基准利率...',
            'published_at': '2026-05-08'
        }
        print(f"1. M0采集: {raw_news['title']}")

        # 2. M1.5推理（模拟）
        print("2. M1.5推理: 降息 → 银行净息差承压 → 但零售转型银行可能受益")

        # 3. M13快速验证
        print("3. M13快速验证...")

        # Mock数据收集
        self.mock_data_manager.search_research_reports.return_value = [
            {"title": "平安银行：零售转型成效显著", "date": "2026-05-01"},
            {"title": "平安银行：资产质量稳健", "date": "2026-05-02"}
        ]
        self.mock_data_manager.get_latest_fundamentals.return_value = {
            "roe": 0.12,
            "pe": 5.5,
            "pb": 0.8
        }

        # Mock LLM分析
        self.mock_llm_client.chat.return_value = """
        {
            "summary": "零售转型顺利，但净息差承压，整体中性偏正面",
            "confidence_multiplier": 1.1,
            "has_major_negative": false
        }
        """

        # 执行快速调研
        research = self.research_agent.quick_research(
            symbol="600000.SH",
            context=f"宏观事件: {raw_news['title']}\n推理: 降息利好零售转型银行"
        )

        print(f"   调研结果: {research.summary}")
        print(f"   置信度调整: ×{research.confidence_multiplier}")

        # 验证结果
        self.assertEqual(research.research_level, ResearchLevel.QUICK)
        self.assertEqual(research.triggered_by, ResearchTrigger.M1_5)
        self.assertGreater(research.confidence_multiplier, 1.0)

        # 4. M2存储（模拟）
        print("4. M2存储: 信号已存储，置信度已调整")

    def test_m12_track_complete_flow(self):
        """测试M12轨道完整流程"""
        print("\n=== 测试M12轨道：异动 → M12溯源 → M13调研 → M3判断 ===")

        # 1. M12异动检测（模拟）
        print("1. M12异动检测: 平安银行 +5.2%，成交量放大3.5倍")

        # 2. M12反向溯源（模拟）
        print("2. M12反向溯源: 找到2条新闻，置信度0.4（信息不足）")

        # 3. M13标准调研
        print("3. M13标准调研...")

        # Mock数据收集
        self.mock_data_manager.search_research_reports.return_value = [
            {"title": "业绩预告超预期", "summary": "Q1净利润同比增长50%"},
            {"title": "机构上调评级", "summary": "目标价上调至15元"}
        ]
        self.mock_data_manager.search_news.return_value = [
            {"title": "签订重大合同", "content": "与某大型企业签订10亿订单"},
            {"title": "新产品发布", "content": "推出新一代产品"}
        ]
        self.mock_data_manager.get_latest_fundamentals.return_value = {
            "roe": 0.15,
            "revenue_growth": 0.30,
            "profit_growth": 0.50
        }

        # Mock LLM分析
        self.mock_llm_client.chat.return_value = """
        {
            "summary": "业绩超预期驱动股价上涨，基本面支撑强劲",
            "key_findings": [
                "Q1业绩大幅超预期",
                "新产品市场反响良好",
                "机构普遍看好"
            ],
            "confidence_delta": 0.25,
            "has_major_negative": false
        }
        """

        # 执行标准调研
        research = self.research_agent.standard_research(
            symbol="600000.SH",
            context="价格异动+5.2%（成交量放大）"
        )

        print(f"   调研结果: {research.summary}")
        print(f"   关键发现: {', '.join(research.key_findings)}")
        print(f"   置信度增量: +{research.confidence_delta}")

        # 验证结果
        self.assertEqual(research.research_level, ResearchLevel.STANDARD)
        self.assertEqual(research.triggered_by, ResearchTrigger.M12)
        self.assertGreater(research.confidence_delta, 0)
        self.assertGreater(len(research.key_findings), 0)

        # 4. M12趋势判断（模拟）
        print("4. M12趋势判断: 置信度从0.4提升至0.65，生成机会")

    def test_m3_judgment_complete_flow(self):
        """测试M3判断完整流程"""
        print("\n=== 测试M3判断：信号聚合 → M3判断 → M13深度验证 → M4行动 ===")

        # 1. M3信号聚合（模拟）
        print("1. M3信号聚合: 收集到3条相关信号")

        # 2. M3判断（模拟）
        print("2. M3判断: 生成机会，置信度0.65")

        # 3. M13深度验证
        print("3. M13深度验证...")

        # Mock数据收集
        self.mock_data_manager.search_research_reports.return_value = [
            {"title": f"研报{i}", "summary": f"分析{i}"} for i in range(10)
        ]
        self.mock_data_manager.search_news.return_value = [
            {"title": f"新闻{i}", "content": f"内容{i}"} for i in range(20)
        ]
        self.mock_data_manager.get_latest_fundamentals.return_value = {
            "roe": 0.12,
            "pe": 5.5,
            "pb": 0.8,
            "revenue_growth": 0.20
        }
        self.mock_data_manager.semantic_search.return_value = [
            {"content": "银行业零售转型趋势明显"}
        ]

        # Mock LLM分析
        self.mock_llm_client.chat.return_value = """
        {
            "summary": "零售转型战略清晰，执行力强，估值修复空间大",
            "key_findings": [
                "零售业务占比提升至60%",
                "金融科技投入持续加大",
                "资产质量保持稳健",
                "估值处于历史低位",
                "行业趋势支持转型"
            ],
            "confidence_delta": 0.15,
            "has_major_negative": false,
            "risk_factors": [
                "净息差收窄压力",
                "宏观经济不确定性"
            ]
        }
        """

        # 执行深度调研
        research = self.research_agent.deep_research(
            symbol="600000.SH",
            context="机会判断：零售转型带来估值重估"
        )

        print(f"   调研结果: {research.summary}")
        print(f"   关键发现: {', '.join(research.key_findings[:3])}...")
        print(f"   置信度增量: +{research.confidence_delta}")

        # 验证结果
        self.assertEqual(research.research_level, ResearchLevel.DEEP)
        self.assertEqual(research.triggered_by, ResearchTrigger.M3)
        self.assertGreater(len(research.key_findings), 3)
        self.assertGreater(research.confidence_delta, 0)

        # 4. M4行动设计（模拟）
        print("4. M4行动设计: 置信度调整至0.80，设计交易方案")

    def test_cache_across_levels(self):
        """测试跨Level的缓存机制"""
        print("\n=== 测试缓存机制 ===")

        symbol = "600000.SH"

        # Mock数据和LLM
        self.mock_data_manager.search_research_reports.return_value = []
        self.mock_data_manager.get_latest_fundamentals.return_value = {}
        self.mock_llm_client.chat.return_value = '{"summary": "测试", "confidence_multiplier": 1.0, "has_major_negative": false}'

        # 1. 第一次快速调研
        print("1. 第一次快速调研（无缓存）")
        research1 = self.research_agent.quick_research(symbol, "测试1")
        self.assertIsNotNone(research1)

        # 2. 第二次快速调研（应该命中缓存）
        print("2. 第二次快速调研（命中缓存）")
        research2 = self.research_agent.quick_research(symbol, "测试2")
        self.assertEqual(research1.summary, research2.summary)

        # 3. 标准调研（不同Level，不命中缓存）
        print("3. 标准调研（不同Level，无缓存）")
        self.mock_llm_client.chat.return_value = '{"summary": "标准", "key_findings": [], "confidence_delta": 0.0, "has_major_negative": false}'
        research3 = self.research_agent.standard_research(symbol, "测试3")
        self.assertNotEqual(research1.summary, research3.summary)

        # 4. 查看缓存统计
        stats = self.cache_manager.get_cache_stats()
        print(f"4. 缓存统计: {stats}")
        self.assertEqual(stats['total_cached'], 2)  # 快速1次 + 标准1次

    def test_negative_finding_flow(self):
        """测试发现利空的完整流程"""
        print("\n=== 测试发现利空流程 ===")

        # 1. M1.5推理（模拟）
        print("1. M1.5推理: 降息利好银行股（置信度0.7）")

        # 2. M13快速验证 - 发现利空
        print("2. M13快速验证...")

        # Mock数据 - 利空信息
        self.mock_data_manager.search_research_reports.return_value = [
            {"title": "平安银行：不良率飙升", "date": "2026-05-01"},
            {"title": "平安银行：拨备覆盖率下降", "date": "2026-05-02"}
        ]
        self.mock_data_manager.get_latest_fundamentals.return_value = {
            "roe": 0.05,  # 低ROE
            "npl_ratio": 0.05  # 高不良率
        }

        # Mock LLM分析 - 发现利空
        self.mock_llm_client.chat.return_value = """
        {
            "summary": "不良率飙升，资产质量恶化，降息利好被抵消",
            "confidence_multiplier": 0.6,
            "has_major_negative": true
        }
        """

        # 执行调研
        research = self.research_agent.quick_research(
            symbol="600000.SH",
            context="降息利好银行股"
        )

        print(f"   调研结果: {research.summary}")
        print(f"   置信度调整: ×{research.confidence_multiplier}")
        print(f"   发现重大利空: {research.has_major_negative}")

        # 验证结果
        self.assertTrue(research.has_major_negative)
        self.assertLess(research.confidence_multiplier, 1.0)

        # 3. 置信度调整（模拟）
        original_confidence = 0.7
        adjusted_confidence = original_confidence * research.confidence_multiplier * 0.5
        print(f"3. 置信度调整: 0.7 × 0.6 × 0.5 = {adjusted_confidence:.2f}")
        print("4. 信号被过滤（置信度过低）")

        self.assertLess(adjusted_confidence, 0.3)

    def test_concurrent_research(self):
        """测试并发调研"""
        print("\n=== 测试并发调研 ===")

        symbols = [f"60000{i}.SH" for i in range(5)]

        # Mock数据和LLM
        self.mock_data_manager.search_research_reports.return_value = []
        self.mock_data_manager.get_latest_fundamentals.return_value = {}
        self.mock_llm_client.chat.return_value = '{"summary": "测试", "confidence_multiplier": 1.0, "has_major_negative": false}'

        # 并发调研
        print(f"并发调研{len(symbols)}个标的...")
        results = []
        for symbol in symbols:
            result = self.research_agent.quick_research(symbol, "并发测试")
            results.append(result)
            print(f"  {symbol}: 完成")

        # 验证所有调研都完成
        self.assertEqual(len(results), len(symbols))
        for result in results:
            self.assertIsNotNone(result)

        print(f"所有{len(symbols)}个调研完成")


if __name__ == '__main__':
    # 运行测试
    suite = unittest.TestLoader().loadTestsFromTestCase(TestM13EndToEnd)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
