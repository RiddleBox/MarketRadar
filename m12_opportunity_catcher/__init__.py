"""
M12 机会补牢模块 (Opportunity Catcher)

价格是最终验证 — 当市场已用真金白银投票时，
反向溯源找原因，判断趋势能否延续，决定是否仍可补上车。

核心流程：
  1. 异动检测 - 扫描全市场价格，识别统计显著异动
  2. 反向溯源 - 对异动股票定向采集新闻，找异动原因
  3. 趋势判断 - 判断异动处于 early/middle/late 阶段
  4. 机会生成 - 输出 RetroOpportunity，供M4行动设计

详见 PRINCIPLES.md 和 DESIGN.md
"""

from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine
from m12_opportunity_catcher.anomaly_detector import AnomalyDetector
from m12_opportunity_catcher.backward_causation import BackwardCausation
from m12_opportunity_catcher.trend_stage import TrendAssessor
from m12_opportunity_catcher.market_strategies import MARKET_STRATEGIES, MarketAnomalyStrategy

__all__ = [
    "OpportunityCatcherEngine",
    "AnomalyDetector",
    "BackwardCausation",
    "TrendAssessor",
    "MARKET_STRATEGIES",
    "MarketAnomalyStrategy",
]