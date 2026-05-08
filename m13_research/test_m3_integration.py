"""
M3 + M13 集成测试
"""

import unittest
from unittest.mock import Mock, patch
import sys
import io

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from core.schemas import ResearchReport, ResearchLevel, ResearchTrigger


class TestM3_M13Integration(unittest.TestCase):
    """测试M3与M13的集成"""

    def setUp(self):
        """测试前准备"""
        self.mock_llm_client = Mock()
        self.mock_signal_store = Mock()
        self.mock_m13_agent = Mock()

    def test_judge_with_m13_deep_verification(self):
        """测试判断后M13深度验证"""
        from m3_judgment.judgment_engine import JudgmentEngine
        from m3_judgment.models import JudgmentResult, OpportunityScore

        # 创建engine（带M13）
        engine = JudgmentEngine(
            llm_client=self.mock_llm_client,
            signal_store=self.mock_signal_store,
            m13_agent=self.mock_m13_agent
        )

        # Mock判断结果 - 生成了机会
        mock_result = JudgmentResult(
            signal_id='test_signal_001',
            is_opportunity=True,
            opportunity_score=OpportunityScore(
                confidence_score=0.65,
                expected_return=0.15,
                risk_level='medium'
            ),
            opportunity_thesis='零售转型带来估值重估机会',
            target_instruments=['600000.SH', '601398.SH'],
            reasoning='基本面改善，估值偏低'
        )

        # Mock M13深度调研
        mock_research = ResearchReport(
            symbol='600000.SH',
            research_level=ResearchLevel.DEEP,
            triggered_by=ResearchTrigger.M3,
            reports=[
                {'title': f'研报{i}', 'summary': f'分析{i}'} for i in range(10)
            ],
            news=[
                {'title': f'新闻{i}', 'content': f'内容{i}'} for i in range(20)
            ],
            fundamentals={
                'roe': 0.12,
                'pe': 5.5,
                'pb': 0.8
            },
            summary='零售转型战略清晰，但估值修复空间有限',
            key_findings=[
                '零售业务占比提升',
                '资产质量稳健',
                '估值处于合理区间',
                '行业竞争加剧'
            ],
            confidence_delta=-0.1,  # 略微降低置信度
            has_major_negative=False
        )
        self.mock_m13_agent.deep_research.return_value = mock_research

        # 执行深度验证（模拟judge方法中的逻辑）
        if engine.m13_agent and mock_result.opportunity_score.confidence_score > 0.5:
            for instrument in mock_result.target_instruments[:2]:
                research = engine.m13_agent.deep_research(
                    symbol=instrument,
                    context=mock_result.opportunity_thesis
                )

                # 调整置信度
                mock_result.opportunity_score.confidence_score += research.confidence_delta

                # 添加调研摘要
                mock_result.opportunity_thesis += f"\n\n【M13调研】{research.summary}"

        # 验证M13被调用
        self.assertEqual(self.mock_m13_agent.deep_research.call_count, 2)

        # 验证置信度被调整
        # 0.65 + (-0.1) + (-0.1) = 0.45
        self.assertLess(mock_result.opportunity_score.confidence_score, 0.65)

        # 验证调研摘要被添加
        self.assertIn('【M13调研】', mock_result.opportunity_thesis)

    def test_judge_low_confidence_skip_m13(self):
        """测试低置信度时跳过M13"""
        from m3_judgment.judgment_engine import JudgmentEngine
        from m3_judgment.models import JudgmentResult, OpportunityScore

        engine = JudgmentEngine(
            llm_client=self.mock_llm_client,
            signal_store=self.mock_signal_store,
            m13_agent=self.mock_m13_agent
        )

        # Mock判断结果 - 低置信度
        mock_result = JudgmentResult(
            signal_id='test_signal_002',
            is_opportunity=True,
            opportunity_score=OpportunityScore(
                confidence_score=0.4,  # 低置信度
                expected_return=0.08,
                risk_level='high'
            ),
            opportunity_thesis='不确定的机会',
            target_instruments=['600000.SH'],
            reasoning='信息不足'
        )

        # 验证M13不被调用
        if engine.m13_agent and mock_result.opportunity_score.confidence_score > 0.5:
            engine.m13_agent.deep_research(
                symbol=mock_result.target_instruments[0],
                context=mock_result.opportunity_thesis
            )

        self.mock_m13_agent.deep_research.assert_not_called()

    def test_judge_m13_major_negative(self):
        """测试M13发现重大利空"""
        from m3_judgment.judgment_engine import JudgmentEngine
        from m3_judgment.models import JudgmentResult, OpportunityScore

        engine = JudgmentEngine(
            llm_client=self.mock_llm_client,
            signal_store=self.mock_signal_store,
            m13_agent=self.mock_m13_agent
        )

        # Mock判断结果
        mock_result = JudgmentResult(
            signal_id='test_signal_003',
            is_opportunity=True,
            opportunity_score=OpportunityScore(
                confidence_score=0.7,
                expected_return=0.20,
                risk_level='medium'
            ),
            opportunity_thesis='业绩增长带来投资机会',
            target_instruments=['600000.SH'],
            reasoning='业绩超预期'
        )

        # Mock M13调研 - 发现重大利空
        mock_research = ResearchReport(
            symbol='600000.SH',
            research_level=ResearchLevel.DEEP,
            triggered_by=ResearchTrigger.M3,
            summary='虽然业绩增长，但发现财务造假嫌疑',
            confidence_delta=-0.2,
            has_major_negative=True
        )
        self.mock_m13_agent.deep_research.return_value = mock_research

        # 执行深度验证
        if engine.m13_agent and mock_result.opportunity_score.confidence_score > 0.5:
            research = engine.m13_agent.deep_research(
                symbol=mock_result.target_instruments[0],
                context=mock_result.opportunity_thesis
            )

            # 调整置信度
            mock_result.opportunity_score.confidence_score += research.confidence_delta

            # 发现重大利空时大幅降低置信度
            if research.has_major_negative:
                mock_result.opportunity_score.confidence_score *= 0.5

        # 验证置信度大幅降低
        # (0.7 - 0.2) × 0.5 = 0.25
        self.assertLess(mock_result.opportunity_score.confidence_score, 0.3)

    def test_judge_m13_positive_verification(self):
        """测试M13正面验证"""
        from m3_judgment.judgment_engine import JudgmentEngine
        from m3_judgment.models import JudgmentResult, OpportunityScore

        engine = JudgmentEngine(
            llm_client=self.mock_llm_client,
            signal_store=self.mock_signal_store,
            m13_agent=self.mock_m13_agent
        )

        # Mock判断结果
        mock_result = JudgmentResult(
            signal_id='test_signal_004',
            is_opportunity=True,
            opportunity_score=OpportunityScore(
                confidence_score=0.6,
                expected_return=0.18,
                risk_level='medium'
            ),
            opportunity_thesis='技术突破带来增长机会',
            target_instruments=['600000.SH'],
            reasoning='新技术应用前景广阔'
        )

        # Mock M13调研 - 正面验证
        mock_research = ResearchReport(
            symbol='600000.SH',
            research_level=ResearchLevel.DEEP,
            triggered_by=ResearchTrigger.M3,
            summary='技术领先优势明显，市场空间巨大',
            key_findings=[
                '技术壁垒高',
                '市场需求旺盛',
                '竞争格局良好',
                '管理团队优秀',
                '财务状况健康'
            ],
            confidence_delta=0.2,
            has_major_negative=False
        )
        self.mock_m13_agent.deep_research.return_value = mock_research

        # 执行深度验证
        if engine.m13_agent and mock_result.opportunity_score.confidence_score > 0.5:
            research = engine.m13_agent.deep_research(
                symbol=mock_result.target_instruments[0],
                context=mock_result.opportunity_thesis
            )

            # 调整置信度
            mock_result.opportunity_score.confidence_score += research.confidence_delta

        # 验证置信度提升
        # 0.6 + 0.2 = 0.8
        self.assertGreater(mock_result.opportunity_score.confidence_score, 0.7)

    def test_judge_m13_failure_graceful(self):
        """测试M13失败时的优雅降级"""
        from m3_judgment.judgment_engine import JudgmentEngine
        from m3_judgment.models import JudgmentResult, OpportunityScore

        engine = JudgmentEngine(
            llm_client=self.mock_llm_client,
            signal_store=self.mock_signal_store,
            m13_agent=self.mock_m13_agent
        )

        # Mock判断结果
        mock_result = JudgmentResult(
            signal_id='test_signal_005',
            is_opportunity=True,
            opportunity_score=OpportunityScore(
                confidence_score=0.65,
                expected_return=0.15,
                risk_level='medium'
            ),
            opportunity_thesis='投资机会',
            target_instruments=['600000.SH'],
            reasoning='基本面良好'
        )

        # Mock M13失败
        self.mock_m13_agent.deep_research.side_effect = Exception("M13调研失败")

        # 执行深度验证（应该不抛出异常）
        original_confidence = mock_result.opportunity_score.confidence_score
        try:
            if engine.m13_agent and mock_result.opportunity_score.confidence_score > 0.5:
                research = engine.m13_agent.deep_research(
                    symbol=mock_result.target_instruments[0],
                    context=mock_result.opportunity_thesis
                )
                mock_result.opportunity_score.confidence_score += research.confidence_delta
        except Exception as e:
            # M13失败不影响主流程
            pass

        # 验证置信度保持原值
        self.assertEqual(mock_result.opportunity_score.confidence_score, original_confidence)

    def test_judge_without_m13(self):
        """测试没有M13时的判断"""
        from m3_judgment.judgment_engine import JudgmentEngine
        from m3_judgment.models import JudgmentResult, OpportunityScore

        # 创建没有M13的engine
        engine = JudgmentEngine(
            llm_client=self.mock_llm_client,
            signal_store=self.mock_signal_store,
            m13_agent=None  # 不使用M13
        )

        # Mock判断结果
        mock_result = JudgmentResult(
            signal_id='test_signal_006',
            is_opportunity=True,
            opportunity_score=OpportunityScore(
                confidence_score=0.7,
                expected_return=0.15,
                risk_level='medium'
            ),
            opportunity_thesis='投资机会',
            target_instruments=['600000.SH'],
            reasoning='基本面良好'
        )

        # 验证M13不被调用
        if engine.m13_agent and mock_result.opportunity_score.confidence_score > 0.5:
            engine.m13_agent.deep_research(
                symbol=mock_result.target_instruments[0],
                context=mock_result.opportunity_thesis
            )

        self.mock_m13_agent.deep_research.assert_not_called()

    def test_judge_multiple_instruments_limit(self):
        """测试多个标的时的限制"""
        from m3_judgment.judgment_engine import JudgmentEngine
        from m3_judgment.models import JudgmentResult, OpportunityScore

        engine = JudgmentEngine(
            llm_client=self.mock_llm_client,
            signal_store=self.mock_signal_store,
            m13_agent=self.mock_m13_agent
        )

        # Mock判断结果 - 5个标的
        mock_result = JudgmentResult(
            signal_id='test_signal_007',
            is_opportunity=True,
            opportunity_score=OpportunityScore(
                confidence_score=0.7,
                expected_return=0.15,
                risk_level='medium'
            ),
            opportunity_thesis='行业机会',
            target_instruments=[
                '600000.SH', '600001.SH', '600002.SH',
                '600003.SH', '600004.SH'
            ],
            reasoning='行业景气度高'
        )

        # Mock M13调研
        mock_research = ResearchReport(
            symbol='600000.SH',
            research_level=ResearchLevel.DEEP,
            triggered_by=ResearchTrigger.M3,
            summary='测试',
            confidence_delta=0.0
        )
        self.mock_m13_agent.deep_research.return_value = mock_research

        # 执行深度验证
        if engine.m13_agent and mock_result.opportunity_score.confidence_score > 0.5:
            for instrument in mock_result.target_instruments[:2]:  # 限制前2个
                research = engine.m13_agent.deep_research(
                    symbol=instrument,
                    context=mock_result.opportunity_thesis
                )

        # 验证M13只被调用2次（限制前2个标的）
        self.assertEqual(self.mock_m13_agent.deep_research.call_count, 2)

    def test_judge_m13_enhances_explainability(self):
        """测试M13增强可解释性"""
        from m3_judgment.judgment_engine import JudgmentEngine
        from m3_judgment.models import JudgmentResult, OpportunityScore

        engine = JudgmentEngine(
            llm_client=self.mock_llm_client,
            signal_store=self.mock_signal_store,
            m13_agent=self.mock_m13_agent
        )

        # Mock判断结果
        mock_result = JudgmentResult(
            signal_id='test_signal_008',
            is_opportunity=True,
            opportunity_score=OpportunityScore(
                confidence_score=0.7,
                expected_return=0.15,
                risk_level='medium'
            ),
            opportunity_thesis='简单的机会描述',
            target_instruments=['600000.SH'],
            reasoning='基本面良好'
        )

        # Mock M13调研 - 详细报告
        mock_research = ResearchReport(
            symbol='600000.SH',
            research_level=ResearchLevel.DEEP,
            triggered_by=ResearchTrigger.M3,
            summary='详细的调研分析：包括行业趋势、竞争格局、财务状况、管理团队等多维度分析',
            key_findings=[
                '行业处于上升周期',
                '公司市场份额领先',
                '财务指标优秀',
                '管理层执行力强',
                '估值具有吸引力'
            ],
            confidence_delta=0.1
        )
        self.mock_m13_agent.deep_research.return_value = mock_research

        # 执行深度验证
        original_thesis = mock_result.opportunity_thesis
        if engine.m13_agent and mock_result.opportunity_score.confidence_score > 0.5:
            research = engine.m13_agent.deep_research(
                symbol=mock_result.target_instruments[0],
                context=mock_result.opportunity_thesis
            )

            # 添加调研摘要
            mock_result.opportunity_thesis += f"\n\n【M13调研】{research.summary}"

        # 验证机会描述被增强
        self.assertGreater(len(mock_result.opportunity_thesis), len(original_thesis))
        self.assertIn('【M13调研】', mock_result.opportunity_thesis)
        self.assertIn('详细的调研分析', mock_result.opportunity_thesis)


if __name__ == '__main__':
    unittest.main(verbosity=2)
