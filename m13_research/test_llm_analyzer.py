"""
M13 LLM Analyzer 单元测试
"""

import unittest
from unittest.mock import Mock, patch
import sys
import io

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from m13_research.llm_analyzer import LLMAnalyzer


class TestLLMAnalyzer(unittest.TestCase):
    """测试LLMAnalyzer功能"""

    def setUp(self):
        """测试前准备"""
        self.mock_llm_client = Mock()
        self.analyzer = LLMAnalyzer(self.mock_llm_client)

    def test_quick_verify_positive(self):
        """测试快速验证 - 正面结果"""
        context = "降息利好银行股"
        report_titles = [
            "平安银行：零售转型成效显著",
            "平安银行：资产质量稳健"
        ]
        fundamentals = {
            "roe": 0.12,
            "pe": 5.5,
            "pb": 0.8
        }

        # Mock LLM响应
        self.mock_llm_client.chat.return_value = """
        {
            "summary": "基本面良好，零售转型顺利，估值合理",
            "confidence_multiplier": 1.2,
            "has_major_negative": false
        }
        """

        # 执行分析
        result = self.analyzer.quick_verify(context, report_titles, fundamentals)

        # 验证结果
        self.assertIn("summary", result)
        self.assertIn("confidence_multiplier", result)
        self.assertIn("has_major_negative", result)
        self.assertGreater(result["confidence_multiplier"], 1.0)
        self.assertFalse(result["has_major_negative"])

    def test_quick_verify_negative(self):
        """测试快速验证 - 发现利空"""
        context = "降息利好银行股"
        report_titles = [
            "平安银行：不良率飙升",
            "平安银行：净息差承压"
        ]
        fundamentals = {
            "roe": 0.05,
            "npl_ratio": 0.05
        }

        # Mock LLM响应
        self.mock_llm_client.chat.return_value = """
        {
            "summary": "不良率飙升，资产质量恶化，降息利好被抵消",
            "confidence_multiplier": 0.6,
            "has_major_negative": true
        }
        """

        # 执行分析
        result = self.analyzer.quick_verify(context, report_titles, fundamentals)

        # 验证结果
        self.assertLess(result["confidence_multiplier"], 1.0)
        self.assertTrue(result["has_major_negative"])

    def test_standard_analyze(self):
        """测试标准分析"""
        context = "价格异动+5.2%"
        reports = [
            {"title": "业绩预告超预期", "summary": "Q1净利润同比增长50%"},
            {"title": "机构上调评级", "summary": "目标价上调至15元"}
        ]
        news = [
            {"title": "签订重大合同", "content": "与某大型企业签订10亿订单"},
            {"title": "新产品发布", "content": "推出新一代产品"}
        ]
        fundamentals = {
            "roe": 0.15,
            "revenue_growth": 0.30,
            "profit_growth": 0.50
        }

        # Mock LLM响应
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

        # 执行分析
        result = self.analyzer.standard_analyze(context, reports, news, fundamentals)

        # 验证结果
        self.assertIn("summary", result)
        self.assertIn("key_findings", result)
        self.assertIn("confidence_delta", result)
        self.assertGreater(len(result["key_findings"]), 0)
        self.assertGreater(result["confidence_delta"], 0)

    def test_deep_analyze(self):
        """测试深度分析"""
        context = "机会判断：零售转型带来估值重估"
        reports = [
            {"title": f"研报{i}", "summary": f"分析{i}"} for i in range(10)
        ]
        news = [
            {"title": f"新闻{i}", "content": f"内容{i}"} for i in range(20)
        ]
        fundamentals = {
            "roe": 0.12,
            "pe": 5.5,
            "pb": 0.8,
            "revenue_growth": 0.20
        }
        industry_trends = [
            {"content": "银行业零售转型趋势明显"},
            {"content": "金融科技赋能零售业务"}
        ]

        # Mock LLM响应
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

        # 执行分析
        result = self.analyzer.deep_analyze(
            context, reports, news, fundamentals, industry_trends
        )

        # 验证结果
        self.assertIn("summary", result)
        self.assertIn("key_findings", result)
        self.assertGreater(len(result["key_findings"]), 3)
        self.assertIn("risk_factors", result)

    def test_parse_json_with_markdown(self):
        """测试解析带markdown代码块的JSON"""
        # Mock LLM响应（带markdown代码块）
        self.mock_llm_client.chat.return_value = """
        ```json
        {
            "summary": "测试",
            "confidence_multiplier": 1.1,
            "has_major_negative": false
        }
        ```
        """

        # 执行分析
        result = self.analyzer.quick_verify("测试", [], {})

        # 验证能正确解析
        self.assertIn("summary", result)
        self.assertEqual(result["summary"], "测试")

    def test_parse_invalid_json(self):
        """测试解析无效JSON的容错"""
        # Mock LLM响应（无效JSON）
        self.mock_llm_client.chat.return_value = "这不是JSON"

        # 执行分析（应该返回默认值）
        result = self.analyzer.quick_verify("测试", [], {})

        # 验证返回了默认值
        self.assertIn("summary", result)
        self.assertIn("confidence_multiplier", result)
        self.assertEqual(result["confidence_multiplier"], 1.0)

    def test_llm_timeout(self):
        """测试LLM超时处理"""
        # Mock LLM超时
        self.mock_llm_client.chat.side_effect = TimeoutError("LLM超时")

        # 执行分析（应该返回默认值）
        result = self.analyzer.quick_verify("测试", [], {})

        # 验证返回了默认值
        self.assertIsInstance(result, dict)
        self.assertIn("confidence_multiplier", result)

    def test_prompt_template_quick(self):
        """测试快速验证Prompt模板"""
        context = "降息利好银行股"
        report_titles = ["研报1", "研报2"]
        fundamentals = {"roe": 0.12}

        # Mock LLM响应
        self.mock_llm_client.chat.return_value = '{"summary": "测试", "confidence_multiplier": 1.0, "has_major_negative": false}'

        # 执行分析
        self.analyzer.quick_verify(context, report_titles, fundamentals)

        # 验证调用了LLM
        self.mock_llm_client.chat.assert_called_once()
        call_args = self.mock_llm_client.chat.call_args

        # 验证Prompt包含关键信息
        prompt = call_args[0][0]
        self.assertIn(context, prompt)
        self.assertIn("研报1", prompt)
        self.assertIn("roe", prompt)

    def test_prompt_template_standard(self):
        """测试标准分析Prompt模板"""
        context = "价格异动+5.2%"
        reports = [{"title": "研报1", "summary": "摘要1"}]
        news = [{"title": "新闻1", "content": "内容1"}]
        fundamentals = {"roe": 0.12}

        # Mock LLM响应
        self.mock_llm_client.chat.return_value = '{"summary": "测试", "key_findings": [], "confidence_delta": 0.0, "has_major_negative": false}'

        # 执行分析
        self.analyzer.standard_analyze(context, reports, news, fundamentals)

        # 验证Prompt包含所有数据
        call_args = self.mock_llm_client.chat.call_args
        prompt = call_args[0][0]
        self.assertIn(context, prompt)
        self.assertIn("研报1", prompt)
        self.assertIn("新闻1", prompt)

    def test_confidence_multiplier_bounds(self):
        """测试置信度乘数边界"""
        # Mock极端值
        self.mock_llm_client.chat.return_value = """
        {
            "summary": "测试",
            "confidence_multiplier": 5.0,
            "has_major_negative": false
        }
        """

        result = self.analyzer.quick_verify("测试", [], {})

        # 验证值被限制在合理范围
        self.assertLessEqual(result["confidence_multiplier"], 2.0)
        self.assertGreaterEqual(result["confidence_multiplier"], 0.5)

    def test_confidence_delta_bounds(self):
        """测试置信度增量边界"""
        # Mock极端值
        self.mock_llm_client.chat.return_value = """
        {
            "summary": "测试",
            "key_findings": [],
            "confidence_delta": 1.0,
            "has_major_negative": false
        }
        """

        result = self.analyzer.standard_analyze("测试", [], [], {})

        # 验证值被限制在合理范围
        self.assertLessEqual(result["confidence_delta"], 0.3)
        self.assertGreaterEqual(result["confidence_delta"], -0.3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
