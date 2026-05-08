"""
M1.5 + M13 集成测试
"""

import unittest
from unittest.mock import Mock, patch
import sys
import io

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from m1_5_implicit_reasoner.inferencer import LLMImplicitSignalInferencer
from m1_5_implicit_reasoner.models import ImplicitSignal
from core.schemas import ResearchReport, ResearchLevel, ResearchTrigger


class TestM1_5_M13Integration(unittest.TestCase):
    """测试M1.5与M13的集成"""

    def setUp(self):
        """测试前准备"""
        self.mock_llm_client = Mock()
        self.mock_industry_graph = Mock()
        self.mock_m13_agent = Mock()

        # 创建inferencer（带M13）
        self.inferencer = LLMImplicitSignalInferencer(
            llm_client=self.mock_llm_client,
            industry_graph=self.mock_industry_graph,
            m13_agent=self.mock_m13_agent
        )

    def test_infer_with_m13_verification(self):
        """测试推理后M13验证"""
        # 准备测试数据
        raw_data = {
            'source': 'xinhua',
            'category': 'policy',
            'title': '央行宣布降息25个基点',
            'content': '为支持实体经济发展...',
            'published_at': '2026-05-08'
        }

        # Mock LLM推理响应
        self.mock_llm_client.chat_json.return_value = {
            'event_analysis': {
                'key_points': ['降息25bp'],
                'event_type': 'monetary_policy',
                'importance': 0.8
            },
            'causal_chain': [
                {
                    'from_concept': '降息',
                    'to_concept': '银行净息差收窄',
                    'relation_type': 'policy_drives',
                    'reasoning': '降息导致贷款利率下降',
                    'confidence': 0.8,
                    'supporting_facts': ['历史数据']
                }
            ],
            'industry_impact': {
                'affected_sectors': [
                    {
                        'sector': '银行',
                        'impact': 'negative',
                        'timeframe': 'short_term'
                    }
                ]
            },
            'target_identification': {
                'opportunities': [
                    {
                        'industry_sector': '银行',
                        'target_symbols': ['600000.SH', '601398.SH'],
                        'opportunity_description': '降息利好银行股',
                        'confidence': 0.7
                    }
                ]
            },
            'overall_assessment': {
                'signal_type': 'policy_driven'
            }
        }

        # Mock M13快速验证 - 发现利空
        mock_research = ResearchReport(
            symbol='600000.SH',
            research_level=ResearchLevel.QUICK,
            triggered_by=ResearchTrigger.M1_5,
            summary='虽然降息，但该银行不良率飙升',
            confidence_multiplier=0.7,
            has_major_negative=True
        )
        self.mock_m13_agent.quick_research.return_value = mock_research

        # 执行推理
        signals = self.inferencer.infer(raw_data)

        # 验证生成了信号
        self.assertGreater(len(signals), 0)
        signal = signals[0]

        # 验证M13被调用
        self.mock_m13_agent.quick_research.assert_called()

        # 验证置信度被调整
        # 原始置信度0.7 × 0.7（multiplier）× 0.5（major_negative）= 0.245
        self.assertLess(signal.prior_confidence, 0.5)

        # 验证调研摘要被添加
        self.assertIn('m13_research', signal.reasoning_chain.reasoning_stages)

    def test_infer_without_m13(self):
        """测试没有M13时的推理"""
        # 创建没有M13的inferencer
        inferencer_no_m13 = LLMImplicitSignalInferencer(
            llm_client=self.mock_llm_client,
            industry_graph=self.mock_industry_graph,
            m13_agent=None  # 不使用M13
        )

        # 准备测试数据
        raw_data = {
            'source': 'xinhua',
            'category': 'policy',
            'title': '央行宣布降息',
            'content': '...',
            'published_at': '2026-05-08'
        }

        # Mock LLM响应
        self.mock_llm_client.chat_json.return_value = {
            'event_analysis': {},
            'causal_chain': [],
            'industry_impact': {'affected_sectors': []},
            'target_identification': {
                'opportunities': [
                    {
                        'industry_sector': '银行',
                        'target_symbols': ['600000.SH'],
                        'opportunity_description': '降息利好',
                        'confidence': 0.7
                    }
                ]
            },
            'overall_assessment': {'signal_type': 'policy_driven'}
        }

        # 执行推理
        signals = inferencer_no_m13.infer(raw_data)

        # 验证生成了信号
        self.assertGreater(len(signals), 0)

        # 验证M13没有被调用
        self.mock_m13_agent.quick_research.assert_not_called()

    def test_infer_low_confidence_skip_m13(self):
        """测试低置信度时跳过M13"""
        # 准备测试数据
        raw_data = {
            'source': 'xinhua',
            'category': 'policy',
            'title': '某政策发布',
            'content': '...',
            'published_at': '2026-05-08'
        }

        # Mock LLM响应 - 低置信度
        self.mock_llm_client.chat_json.return_value = {
            'event_analysis': {},
            'causal_chain': [],
            'industry_impact': {'affected_sectors': []},
            'target_identification': {
                'opportunities': [
                    {
                        'industry_sector': '某行业',
                        'target_symbols': ['600000.SH'],
                        'opportunity_description': '可能受益',
                        'confidence': 0.3  # 低置信度
                    }
                ]
            },
            'overall_assessment': {'signal_type': 'policy_driven'}
        }

        # 执行推理
        signals = self.inferencer.infer(raw_data)

        # 验证生成了信号
        self.assertGreater(len(signals), 0)

        # 验证M13没有被调用（置信度 < 0.5）
        self.mock_m13_agent.quick_research.assert_not_called()

    def test_infer_m13_positive_verification(self):
        """测试M13正面验证"""
        # 准备测试数据
        raw_data = {
            'source': 'xinhua',
            'category': 'policy',
            'title': '新能源政策利好',
            'content': '...',
            'published_at': '2026-05-08'
        }

        # Mock LLM响应
        self.mock_llm_client.chat_json.return_value = {
            'event_analysis': {},
            'causal_chain': [],
            'industry_impact': {'affected_sectors': []},
            'target_identification': {
                'opportunities': [
                    {
                        'industry_sector': '新能源',
                        'target_symbols': ['600000.SH'],
                        'opportunity_description': '政策利好',
                        'confidence': 0.6
                    }
                ]
            },
            'overall_assessment': {'signal_type': 'policy_driven'}
        }

        # Mock M13验证 - 正面结果
        mock_research = ResearchReport(
            symbol='600000.SH',
            research_level=ResearchLevel.QUICK,
            triggered_by=ResearchTrigger.M1_5,
            summary='基本面良好，政策支持明确',
            confidence_multiplier=1.3,
            has_major_negative=False
        )
        self.mock_m13_agent.quick_research.return_value = mock_research

        # 执行推理
        signals = self.inferencer.infer(raw_data)

        # 验证置信度被提升
        signal = signals[0]
        # 原始置信度应该被乘以1.3
        self.assertGreater(signal.prior_confidence, 0.6)

    def test_infer_m13_failure_graceful(self):
        """测试M13失败时的优雅降级"""
        # 准备测试数据
        raw_data = {
            'source': 'xinhua',
            'category': 'policy',
            'title': '某政策发布',
            'content': '...',
            'published_at': '2026-05-08'
        }

        # Mock LLM响应
        self.mock_llm_client.chat_json.return_value = {
            'event_analysis': {},
            'causal_chain': [],
            'industry_impact': {'affected_sectors': []},
            'target_identification': {
                'opportunities': [
                    {
                        'industry_sector': '某行业',
                        'target_symbols': ['600000.SH'],
                        'opportunity_description': '可能受益',
                        'confidence': 0.7
                    }
                ]
            },
            'overall_assessment': {'signal_type': 'policy_driven'}
        }

        # Mock M13失败
        self.mock_m13_agent.quick_research.side_effect = Exception("M13调研失败")

        # 执行推理（应该不抛出异常）
        signals = self.inferencer.infer(raw_data)

        # 验证仍然生成了信号
        self.assertGreater(len(signals), 0)

        # 验证置信度保持原值（没有被M13调整）
        signal = signals[0]
        self.assertAlmostEqual(signal.prior_confidence, 0.7, places=1)

    def test_infer_multiple_targets_limit(self):
        """测试多个标的时的限制"""
        # 准备测试数据
        raw_data = {
            'source': 'xinhua',
            'category': 'policy',
            'title': '行业政策利好',
            'content': '...',
            'published_at': '2026-05-08'
        }

        # Mock LLM响应 - 5个标的
        self.mock_llm_client.chat_json.return_value = {
            'event_analysis': {},
            'causal_chain': [],
            'industry_impact': {'affected_sectors': []},
            'target_identification': {
                'opportunities': [
                    {
                        'industry_sector': '某行业',
                        'target_symbols': [
                            '600000.SH', '600001.SH', '600002.SH',
                            '600003.SH', '600004.SH'
                        ],
                        'opportunity_description': '行业利好',
                        'confidence': 0.7
                    }
                ]
            },
            'overall_assessment': {'signal_type': 'policy_driven'}
        }

        # Mock M13验证
        mock_research = ResearchReport(
            symbol='600000.SH',
            research_level=ResearchLevel.QUICK,
            triggered_by=ResearchTrigger.M1_5,
            summary='测试',
            confidence_multiplier=1.0
        )
        self.mock_m13_agent.quick_research.return_value = mock_research

        # 执行推理
        signals = self.inferencer.infer(raw_data)

        # 验证M13只被调用3次（限制前3个标的）
        self.assertEqual(self.mock_m13_agent.quick_research.call_count, 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
