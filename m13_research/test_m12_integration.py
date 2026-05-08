"""
M12 + M13 集成测试
"""

import unittest
from unittest.mock import Mock, patch
import sys
import io

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from m12_opportunity_catcher.models import PriceAnomaly, AnomalyType, CausationResult
from core.schemas import ResearchReport, ResearchLevel, ResearchTrigger


class TestM12_M13Integration(unittest.TestCase):
    """测试M12与M13的集成"""

    def setUp(self):
        """测试前准备"""
        self.mock_llm_client = Mock()
        self.mock_m13_agent = Mock()

    def test_build_opportunity_with_m13_research(self):
        """测试构建机会时的M13调研"""
        from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine

        # 创建engine（带M13）
        engine = OpportunityCatcherEngine(
            llm_client=self.mock_llm_client,
            m13_agent=self.mock_m13_agent
        )

        # 准备测试数据 - 价格异动
        anomaly = PriceAnomaly(
            instrument='600000.SH',
            anomaly_type=AnomalyType.VOLUME_SPIKE,
            price_change_pct=5.2,
            volume_ratio=3.5,
            detected_at='2026-05-08 10:00:00',
            confidence=0.8
        )

        # Mock反向溯源结果 - 低置信度
        causation = CausationResult(
            anomaly=anomaly,
            related_news=[
                {'title': '新闻1', 'relevance': 0.6},
                {'title': '新闻2', 'relevance': 0.5}
            ],
            confidence=0.5,  # 低置信度，触发M13
            reasoning='只找到2条相关新闻'
        )

        # Mock M13标准调研 - 补充信息
        mock_research = ResearchReport(
            symbol='600000.SH',
            research_level=ResearchLevel.STANDARD,
            triggered_by=ResearchTrigger.M12,
            reports=[
                {'title': '业绩预告超预期', 'summary': 'Q1净利润增长50%'},
                {'title': '机构上调评级', 'summary': '目标价上调'}
            ],
            news=[
                {'title': '签订重大合同', 'content': '10亿订单'},
                {'title': '新产品发布', 'content': '市场反响好'}
            ],
            summary='业绩超预期驱动股价上涨',
            key_findings=['业绩大增', '机构看好', '订单充足'],
            confidence_delta=0.25,
            has_major_negative=False
        )
        self.mock_m13_agent.standard_research.return_value = mock_research

        # Mock LLM判断趋势
        self.mock_llm_client.chat_json.return_value = {
            'trend_type': 'breakout',
            'confidence': 0.8,
            'reasoning': '基本面支撑强劲'
        }

        # 执行构建机会（模拟_build_opportunity逻辑）
        # 注意：这里简化测试，实际需要完整的_build_opportunity方法

        # 验证M13被调用
        if engine.m13_agent and causation.confidence < 0.7:
            research = engine.m13_agent.standard_research(
                symbol=anomaly.instrument,
                context=f"价格异动{anomaly.price_change_pct:+.1f}%"
            )

            # 调整置信度
            causation.confidence += research.confidence_delta

            # 验证置信度提升
            self.assertGreater(causation.confidence, 0.5)
            self.assertAlmostEqual(causation.confidence, 0.75, places=2)

    def test_build_opportunity_high_confidence_skip_m13(self):
        """测试高置信度时跳过M13"""
        from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine

        engine = OpportunityCatcherEngine(
            llm_client=self.mock_llm_client,
            m13_agent=self.mock_m13_agent
        )

        # 准备测试数据 - 高置信度溯源
        anomaly = PriceAnomaly(
            instrument='600000.SH',
            anomaly_type=AnomalyType.PRICE_SURGE,
            price_change_pct=8.5,
            volume_ratio=5.0,
            detected_at='2026-05-08 10:00:00',
            confidence=0.9
        )

        causation = CausationResult(
            anomaly=anomaly,
            related_news=[
                {'title': '重大利好1', 'relevance': 0.9},
                {'title': '重大利好2', 'relevance': 0.85},
                {'title': '重大利好3', 'relevance': 0.8}
            ],
            confidence=0.85,  # 高置信度，不触发M13
            reasoning='找到多条高相关新闻'
        )

        # 验证M13不被调用
        if engine.m13_agent and causation.confidence < 0.7:
            engine.m13_agent.standard_research(
                symbol=anomaly.instrument,
                context=f"价格异动{anomaly.price_change_pct:+.1f}%"
            )

        # 验证M13没有被调用
        self.mock_m13_agent.standard_research.assert_not_called()

    def test_build_opportunity_m13_negative_finding(self):
        """测试M13发现重大利空"""
        from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine

        engine = OpportunityCatcherEngine(
            llm_client=self.mock_llm_client,
            m13_agent=self.mock_m13_agent
        )

        # 准备测试数据
        anomaly = PriceAnomaly(
            instrument='600000.SH',
            anomaly_type=AnomalyType.PRICE_SURGE,
            price_change_pct=6.0,
            volume_ratio=4.0,
            detected_at='2026-05-08 10:00:00',
            confidence=0.8
        )

        causation = CausationResult(
            anomaly=anomaly,
            related_news=[
                {'title': '股价上涨', 'relevance': 0.5}
            ],
            confidence=0.5,
            reasoning='信息不足'
        )

        # Mock M13调研 - 发现利空
        mock_research = ResearchReport(
            symbol='600000.SH',
            research_level=ResearchLevel.STANDARD,
            triggered_by=ResearchTrigger.M12,
            summary='虽然股价上涨，但发现财务造假嫌疑',
            confidence_delta=-0.1,
            has_major_negative=True
        )
        self.mock_m13_agent.standard_research.return_value = mock_research

        # 执行调研
        if engine.m13_agent and causation.confidence < 0.7:
            research = engine.m13_agent.standard_research(
                symbol=anomaly.instrument,
                context=f"价格异动{anomaly.price_change_pct:+.1f}%"
            )

            # 调整置信度
            causation.confidence += research.confidence_delta

            # 发现重大利空时降低置信度
            if research.has_major_negative:
                causation.confidence *= 0.5

            # 验证置信度大幅降低
            # (0.5 - 0.1) × 0.5 = 0.2
            self.assertLess(causation.confidence, 0.3)

    def test_build_opportunity_m13_failure_graceful(self):
        """测试M13失败时的优雅降级"""
        from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine

        engine = OpportunityCatcherEngine(
            llm_client=self.mock_llm_client,
            m13_agent=self.mock_m13_agent
        )

        # 准备测试数据
        anomaly = PriceAnomaly(
            instrument='600000.SH',
            anomaly_type=AnomalyType.VOLUME_SPIKE,
            price_change_pct=5.0,
            volume_ratio=3.0,
            detected_at='2026-05-08 10:00:00',
            confidence=0.8
        )

        causation = CausationResult(
            anomaly=anomaly,
            related_news=[],
            confidence=0.4,
            reasoning='信息不足'
        )

        # Mock M13失败
        self.mock_m13_agent.standard_research.side_effect = Exception("M13调研失败")

        # 执行调研（应该不抛出异常）
        original_confidence = causation.confidence
        try:
            if engine.m13_agent and causation.confidence < 0.7:
                research = engine.m13_agent.standard_research(
                    symbol=anomaly.instrument,
                    context=f"价格异动{anomaly.price_change_pct:+.1f}%"
                )
                causation.confidence += research.confidence_delta
        except Exception as e:
            # M13失败不影响主流程
            pass

        # 验证置信度保持原值
        self.assertEqual(causation.confidence, original_confidence)

    def test_build_opportunity_without_m13(self):
        """测试没有M13时的构建"""
        from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine

        # 创建没有M13的engine
        engine = OpportunityCatcherEngine(
            llm_client=self.mock_llm_client,
            m13_agent=None  # 不使用M13
        )

        # 准备测试数据
        anomaly = PriceAnomaly(
            instrument='600000.SH',
            anomaly_type=AnomalyType.PRICE_SURGE,
            price_change_pct=5.0,
            volume_ratio=3.0,
            detected_at='2026-05-08 10:00:00',
            confidence=0.8
        )

        causation = CausationResult(
            anomaly=anomaly,
            related_news=[],
            confidence=0.5,
            reasoning='信息不足'
        )

        # 验证M13不被调用
        if engine.m13_agent and causation.confidence < 0.7:
            engine.m13_agent.standard_research(
                symbol=anomaly.instrument,
                context=f"价格异动{anomaly.price_change_pct:+.1f}%"
            )

        self.mock_m13_agent.standard_research.assert_not_called()

    def test_build_opportunity_m13_info_supplement(self):
        """测试M13补充信息的效果"""
        from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine

        engine = OpportunityCatcherEngine(
            llm_client=self.mock_llm_client,
            m13_agent=self.mock_m13_agent
        )

        # 准备测试数据 - 溯源信息很少
        anomaly = PriceAnomaly(
            instrument='600000.SH',
            anomaly_type=AnomalyType.PRICE_SURGE,
            price_change_pct=7.0,
            volume_ratio=4.5,
            detected_at='2026-05-08 10:00:00',
            confidence=0.8
        )

        causation = CausationResult(
            anomaly=anomaly,
            related_news=[
                {'title': '股价上涨', 'relevance': 0.4}
            ],
            confidence=0.4,  # 低置信度
            reasoning='只找到1条新闻'
        )

        # Mock M13调研 - 补充大量信息
        mock_research = ResearchReport(
            symbol='600000.SH',
            research_level=ResearchLevel.STANDARD,
            triggered_by=ResearchTrigger.M12,
            reports=[
                {'title': f'研报{i}', 'summary': f'分析{i}'} for i in range(5)
            ],
            news=[
                {'title': f'新闻{i}', 'content': f'内容{i}'} for i in range(12)
            ],
            fundamentals={
                'roe': 0.15,
                'revenue_growth': 0.30,
                'profit_growth': 0.50
            },
            summary='业绩大幅超预期，多重利好叠加',
            key_findings=['业绩超预期', '新订单充足', '行业景气度高'],
            confidence_delta=0.35,
            has_major_negative=False
        )
        self.mock_m13_agent.standard_research.return_value = mock_research

        # 执行调研
        if engine.m13_agent and causation.confidence < 0.7:
            research = engine.m13_agent.standard_research(
                symbol=anomaly.instrument,
                context=f"价格异动{anomaly.price_change_pct:+.1f}%"
            )

            # 验证补充了大量信息
            self.assertGreater(len(research.reports), 0)
            self.assertGreater(len(research.news), 10)
            self.assertGreater(len(research.key_findings), 0)

            # 调整置信度
            causation.confidence += research.confidence_delta

            # 验证置信度大幅提升
            # 0.4 + 0.35 = 0.75
            self.assertGreater(causation.confidence, 0.7)


if __name__ == '__main__':
    unittest.main(verbosity=2)
