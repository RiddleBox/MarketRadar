"""
M12 机会补牢模块 (Opportunity Catcher)

价格是最终验证 — 当市场已用真金白银投票时，
反向溯源找原因，判断趋势能否延续，决定是否仍可补上车。
"""

from m12_opportunity_catcher.anomaly_detector import AnomalyDetector
from m12_opportunity_catcher.backward_causation import BackwardCausation
from m12_opportunity_catcher.trend_stage import TrendAssessor
from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine
from m12_opportunity_catcher.market_strategies import MARKET_STRATEGIES, MarketAnomalyStrategy, get_strategy

__all__ = [
    "OpportunityCatcherEngine",
    "AnomalyDetector",
    "BackwardCausation",
    "TrendAssessor",
    "MARKET_STRATEGIES",
    "MarketAnomalyStrategy",
    "get_strategy",
]