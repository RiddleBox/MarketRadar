"""
M1.5 隐性信号推理模块
从非财经信息中提取隐性投资机会

核心功能:
- 多阶因果推理: 事件 → 因果链 → 产业影响 → 具体标的
- 推理链可追溯性: 完整记录推理过程供人工审核
- 初始置信度计算: 基于推理链强度计算先验概率
- 输出结构化隐性信号供M3二次验证
"""

from m1_5_implicit_reasoner.models import (
    ImplicitSignal,
    ReasoningChain,
    CausalLink,
    ReasoningStage
)
from m1_5_implicit_reasoner.inferencer import ImplicitSignalInferencer

__all__ = [
    'ImplicitSignal',
    'ReasoningChain',
    'CausalLink',
    'ReasoningStage',
    'ImplicitSignalInferencer'
]
