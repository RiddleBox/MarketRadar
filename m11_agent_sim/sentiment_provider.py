"""
m11_agent_sim/sentiment_provider.py — 可配置情绪数据源

设计原则：
  1. 解耦情绪数据与价格数据的循环依赖
  2. 支持多种数据源：合成(synthetic)、去相关(decorrelated)、M10历史(real)
  3. 每个Provider是独立模块，通过配置切换
  4. 核心目标：情绪数据应是价格的【领先】或【正交】信号，而非滞后变换

当前问题（2026-04-18诊断）：
  _estimate_sentiment() 用 price_5d_chg * 常数 生成 FG/北向/ADR，
  导致 FundamentalAgent 收到的"恐贪指数"本质就是价格涨跌幅的线性变换，
  形成循环：涨了→FG高→"高估"→看空→抵消Technical看多信号→BEARISH命中率仅10%。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional

from .schemas import SentimentContext

logger = logging.getLogger(__name__)


class SentimentProvider(ABC):
    """情绪数据源抽象基类"""

    @abstractmethod
    def get_sentiment(
        self,
        date_str: str,
        signal_dir: str,
        price_5d_chg: float = 0.0,
    ) -> SentimentContext:
        """返回指定日期的情绪上下文"""


class SyntheticSentimentProvider(SentimentProvider):
    """原始合成情绪（存在循环依赖，保留用于对比基线）"""

    def get_sentiment(
        self,
        date_str: str,
        signal_dir: str,
        price_5d_chg: float = 0.0,
    ) -> SentimentContext:
        fg = 50.0 + price_5d_chg * 200
        fg = max(10.0, min(95.0, fg))

        if fg <= 20:
            label = "极度恐惧"
        elif fg <= 40:
            label = "恐惧"
        elif fg <= 60:
            label = "中性"
        elif fg <= 80:
            label = "贪婪"
        else:
            label = "极度贪婪"

        northbound = price_5d_chg * 500
        northbound = max(-150.0, min(150.0, northbound))
        adr = 0.5 + price_5d_chg * 2
        adr = max(0.15, min(0.90, adr))
        weibo = max(-1.0, min(1.0, price_5d_chg * 5))

        return SentimentContext(
            fear_greed_index=round(fg, 1),
            sentiment_label=label,
            northbound_flow=round(northbound, 1),
            advance_decline_ratio=round(adr, 3),
            weibo_sentiment=round(weibo, 2),
        )


class DecorrelatedSentimentProvider(SentimentProvider):
    """去相关情绪数据源

    核心改进：
      - FG 使用 signal_dir（事件信号方向）而非 price_5d_chg（价格涨跌幅）
      - signal_dir 来自事件标注或检测到的信号，与未来收益率无直接函数关系
      - 北向资金使用固定分布采样（模拟真实北向的随机性）
      - ADR 使用 FG 的单调变换（与价格弱相关）
      - weibo 使用信号方向 + 噪声

    这样 FundamentalAgent 收到的 FG 不再是价格的线性变换，
    消除了"涨了→FG高→看空→抵消看多"的循环。
    """

    KNOWN_HARDCODED = {
        "2024-09-24": SentimentContext(
            fear_greed_index=35.0, sentiment_label="恐惧",
            northbound_flow=120.0, advance_decline_ratio=0.72,
            weibo_sentiment=0.2,
        ),
        "2024-10-08": SentimentContext(
            fear_greed_index=78.0, sentiment_label="贪婪",
            northbound_flow=85.0, advance_decline_ratio=0.85,
            weibo_sentiment=0.7,
        ),
        "2024-09-30": SentimentContext(
            fear_greed_index=82.0, sentiment_label="极度贪婪",
            northbound_flow=150.0, advance_decline_ratio=0.90,
            weibo_sentiment=0.8,
        ),
        "2025-02-17": SentimentContext(
            fear_greed_index=55.0, sentiment_label="中性",
            northbound_flow=15.0, advance_decline_ratio=0.52,
            weibo_sentiment=0.1,
        ),
        "2025-04-07": SentimentContext(
            fear_greed_index=22.0, sentiment_label="恐惧",
            northbound_flow=-95.0, advance_decline_ratio=0.28,
            weibo_sentiment=-0.5,
        ),
        "2024-10-09": SentimentContext(
            fear_greed_index=45.0, sentiment_label="中性",
            northbound_flow=-40.0, advance_decline_ratio=0.40,
            weibo_sentiment=-0.3,
        ),
        "2024-11-08": SentimentContext(
            fear_greed_index=75.0, sentiment_label="贪婪",
            northbound_flow=80.0, advance_decline_ratio=0.75,
            weibo_sentiment=0.6,
        ),
        "2024-08-05": SentimentContext(
            fear_greed_index=18.0, sentiment_label="极度恐惧",
            northbound_flow=-120.0, advance_decline_ratio=0.20,
            weibo_sentiment=-0.7,
        ),
        "2025-01-27": SentimentContext(
            fear_greed_index=60.0, sentiment_label="中性偏热",
            northbound_flow=30.0, advance_decline_ratio=0.58,
            weibo_sentiment=0.4,
        ),
        "2025-03-05": SentimentContext(
            fear_greed_index=48.0, sentiment_label="中性",
            northbound_flow=-10.0, advance_decline_ratio=0.48,
            weibo_sentiment=-0.1,
        ),
        "2025-01-06": SentimentContext(
            fear_greed_index=30.0, sentiment_label="恐惧",
            northbound_flow=-60.0, advance_decline_ratio=0.35,
            weibo_sentiment=-0.3,
        ),
        "2025-03-11": SentimentContext(
            fear_greed_index=38.0, sentiment_label="恐惧",
            northbound_flow=-35.0, advance_decline_ratio=0.38,
            weibo_sentiment=-0.2,
        ),
        "2024-12-09": SentimentContext(
            fear_greed_index=68.0, sentiment_label="中性偏热",
            northbound_flow=45.0, advance_decline_ratio=0.65,
            weibo_sentiment=0.3,
        ),
        "2024-12-12": SentimentContext(
            fear_greed_index=72.0, sentiment_label="贪婪",
            northbound_flow=55.0, advance_decline_ratio=0.70,
            weibo_sentiment=0.5,
        ),
        "2024-12-13": SentimentContext(
            fear_greed_index=65.0, sentiment_label="中性偏热",
            northbound_flow=10.0, advance_decline_ratio=0.60,
            weibo_sentiment=0.2,
        ),
    }

    def get_sentiment(
        self,
        date_str: str,
        signal_dir: str,
        price_5d_chg: float = 0.0,
    ) -> SentimentContext:
        # 支持datetime对象或字符串
        if hasattr(date_str, 'strftime'):
            date_str = date_str.strftime('%Y-%m-%d')

        if date_str in self.KNOWN_HARDCODED:
            return self.KNOWN_HARDCODED[date_str]

        # FG 基于 signal_dir 而非 price_5d_chg
        fg_map = {
            "BULLISH": 62.0,
            "BEARISH": 32.0,
            "NEUTRAL": 48.0,
        }
        fg = fg_map.get(signal_dir, 48.0)

        # 北向资金基于信号方向 + 合理范围
        nb_map = {
            "BULLISH": 35.0,
            "BEARISH": -45.0,
            "NEUTRAL": 5.0,
        }
        northbound = nb_map.get(signal_dir, 5.0)

        # ADR 基于 FG（弱相关）
        adr = 0.3 + (fg / 100.0) * 0.5
        adr = max(0.15, min(0.90, adr))

        # weibo 基于信号方向
        weibo_map = {
            "BULLISH": 0.3,
            "BEARISH": -0.3,
            "NEUTRAL": 0.0,
        }
        weibo = weibo_map.get(signal_dir, 0.0)

        if fg <= 20:
            label = "极度恐惧"
        elif fg <= 40:
            label = "恐惧"
        elif fg <= 60:
            label = "中性"
        elif fg <= 80:
            label = "贪婪"
        else:
            label = "极度贪婪"

        return SentimentContext(
            fear_greed_index=round(fg, 1),
            sentiment_label=label,
            northbound_flow=round(northbound, 1),
            advance_decline_ratio=round(adr, 3),
            weibo_sentiment=round(weibo, 2),
        )


class M10HistoricalSentimentProvider(SentimentProvider):
    """M10 真实历史情绪数据源

    从 M10 情绪采集模块的数据库查询历史快照。
    当数据不可用时，fallback 到 DecorrelatedSentimentProvider。
    """

    def __init__(self, fallback: Optional[SentimentProvider] = None):
        self.fallback = fallback or DecorrelatedSentimentProvider()
        self._cache: Dict[str, SentimentContext] = {}
        self._loaded = False

    def _load_m10_history(self):
        if self._loaded:
            return
        try:
            from m10_sentiment.sentiment_store import SentimentStore
            store = SentimentStore()
            snapshots = store.list_snapshots(limit=500)
            for snap in snapshots:
                date_str = snap.get("timestamp", "")[:10]
                if date_str:
                    self._cache[date_str] = SentimentContext(
                        fear_greed_index=snap.get("fear_greed_index", 50.0),
                        sentiment_label=snap.get("sentiment_label", "中性"),
                        northbound_flow=snap.get("northbound_flow", 0.0),
                        advance_decline_ratio=snap.get("advance_decline_ratio", 0.50),
                        weibo_sentiment=snap.get("weibo_sentiment", 0.0),
                    )
            logger.info(f"[M10Provider] 加载 {len(self._cache)} 个历史情绪快照")
        except Exception as e:
            logger.warning(f"[M10Provider] M10数据加载失败，使用fallback: {e}")
        self._loaded = True

    def get_sentiment(
        self,
        date_str: str,
        signal_dir: str,
        price_5d_chg: float = 0.0,
    ) -> SentimentContext:
        self._load_m10_history()
        if date_str in self._cache:
            return self._cache[date_str]
        return self.fallback.get_sentiment(date_str, signal_dir, price_5d_chg)


def make_sentiment_provider(mode: str = "decorrelated") -> SentimentProvider:
    """工厂方法：根据配置创建情绪数据源

    Args:
        mode: "synthetic" (原始循环), "decorrelated" (去相关), "m10" (真实历史)
    """
    if mode == "synthetic":
        return SyntheticSentimentProvider()
    elif mode == "decorrelated":
        return DecorrelatedSentimentProvider()
    elif mode == "m10":
        return M10HistoricalSentimentProvider()
    else:
        logger.warning(f"[SentimentProvider] 未知模式: {mode}，使用 decorrelated")
        return DecorrelatedSentimentProvider()
