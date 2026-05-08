"""
M13 Research Agent — 深度调研模块

主动搜索验证信息，提升决策质量。

核心组件：
- ResearchAgent: 调研引擎
- LLMAnalyzer: LLM分析器
- CacheManager: 缓存管理器
"""

from m13_research.research_agent import ResearchAgent
from m13_research.llm_analyzer import LLMAnalyzer
from m13_research.cache_manager import CacheManager

__all__ = ['ResearchAgent', 'LLMAnalyzer', 'CacheManager']
