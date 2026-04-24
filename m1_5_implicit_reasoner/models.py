"""
M1.5 隐性信号推理数据模型
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum


class ReasoningStage(Enum):
    """推理阶段"""
    EVENT_ANALYSIS = "event_analysis"  # 事件分析
    CAUSAL_INFERENCE = "causal_inference"  # 因果推断
    INDUSTRY_IMPACT = "industry_impact"  # 产业影响
    TARGET_IDENTIFICATION = "target_identification"  # 标的识别


@dataclass
class CausalLink:
    """因果链条中的单个环节"""
    from_concept: str  # 起始概念
    to_concept: str  # 目标概念
    relation_type: str  # 关系类型: policy_drives, tech_enables, demand_shifts
    confidence: float  # 该环节置信度 [0-1]
    reasoning: str  # 推理依据
    supporting_facts: List[str] = field(default_factory=list)  # 支撑事实


@dataclass
class ReasoningChain:
    """完整推理链"""
    chain_id: str
    source_event: str  # 源事件描述
    target_opportunity: str  # 目标机会描述
    causal_links: List[CausalLink]  # 因果链条
    reasoning_stages: Dict[ReasoningStage, str]  # 各阶段推理过程
    overall_confidence: float  # 整体置信度
    created_at: datetime = field(default_factory=datetime.now)

    def get_chain_strength(self) -> float:
        """计算推理链强度 (所有环节置信度的几何平均)"""
        if not self.causal_links:
            return 0.0
        product = 1.0
        for link in self.causal_links:
            product *= link.confidence
        return product ** (1.0 / len(self.causal_links))


@dataclass
class ImplicitSignal:
    """隐性信号 (M1.5输出)"""
    signal_id: str
    signal_type: str  # policy_driven, tech_breakthrough, social_trend
    source_info: Dict  # 源信息 (来自M0)
    reasoning_chain: ReasoningChain  # 推理链

    # 机会识别
    industry_sector: str  # 产业板块
    target_symbols: List[str]  # 潜在标的代码
    opportunity_description: str  # 机会描述

    # 置信度 (先验概率)
    prior_confidence: float  # 基于推理链强度的初始置信度

    # 时间窗口
    expected_impact_timeframe: str  # 预期影响时间: immediate, short_term, mid_term, long_term

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    requires_m3_validation: bool = True  # 是否需要M3验证

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'signal_id': self.signal_id,
            'signal_type': self.signal_type,
            'source_info': self.source_info,
            'reasoning_chain': {
                'chain_id': self.reasoning_chain.chain_id,
                'source_event': self.reasoning_chain.source_event,
                'target_opportunity': self.reasoning_chain.target_opportunity,
                'causal_links': [
                    {
                        'from': link.from_concept,
                        'to': link.to_concept,
                        'relation': link.relation_type,
                        'confidence': link.confidence,
                        'reasoning': link.reasoning
                    }
                    for link in self.reasoning_chain.causal_links
                ],
                'overall_confidence': self.reasoning_chain.overall_confidence
            },
            'industry_sector': self.industry_sector,
            'target_symbols': self.target_symbols,
            'opportunity_description': self.opportunity_description,
            'prior_confidence': self.prior_confidence,
            'expected_impact_timeframe': self.expected_impact_timeframe,
            'created_at': self.created_at.isoformat(),
            'requires_m3_validation': self.requires_m3_validation
        }
