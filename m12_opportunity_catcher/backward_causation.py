"""
m12_opportunity_catcher/backward_causation.py — 反向溯源

设计原则（见 PRINCIPLES.md）：
  2. 溯因必须有证据 — 每次补牢必须连到明确原因
  找不到原因的异动 = 放弃，无因追高 = 赌博

反向溯源流程：
  1. M0定向采集（按股票代码采集新闻）
  2. M1解码（对采集到的新闻运行SignalDecoder）
  3. M10情绪（获取恐贪指数作为背景）
  4. 溯源置信度评估（完全解释/部分解释/无法解释）
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from core.schemas import (
    CausationResult,
    Direction,
    Market,
    PriceAnomaly,
    SignalType,
    SourceType,
    MarketSignal,
    SignalLogicFrame,
    TimeHorizon,
)

logger = logging.getLogger(__name__)


class BackwardCausation:
    """反向溯源器"""

    CAUSATION_TYPE_MAP = {
        "policy": SignalType.POLICY,
        "industry": SignalType.INDUSTRY,
        "earnings": SignalType.EVENT_DRIVEN,
        "capital_flow": SignalType.CAPITAL_FLOW,
        "technical": SignalType.TECHNICAL,
        "macro": SignalType.MACRO,
    }

    def __init__(self, llm_client=None, news_providers: dict = None):
        self.llm_client = llm_client
        self.news_providers = news_providers or {}

    def trace(
        self,
        anomaly: PriceAnomaly,
        historical_signals: Optional[List[MarketSignal]] = None,
        sentiment_data: Optional[Dict] = None,
    ) -> CausationResult:
        """反向溯源主流程

        Args:
            anomaly: 价格异动事件
            historical_signals: M2中近期相关信号
            sentiment_data: M10情绪数据

        Returns:
            CausationResult 溯源结果
        """
        causes = []

        # Step 1: 从历史信号中查找相关信号
        if historical_signals:
            rel_signals = self._find_related_signals(anomaly, historical_signals)
            causes.extend(rel_signals)

        # Step 2: 定向采集新闻（如果signals不足）
        if len(causes) < 2:
            news_signals = self._collect_targeted_news(anomaly)
            causes.extend(news_signals)

        # Step 3: 评估溯源置信度
        confidence, unexplained_ratio, causation_type = self._assess_confidence(
            anomaly, causes, sentiment_data
        )

        return CausationResult(
            anomaly=anomaly,
            causes=causes,
            unexplained_ratio=unexplained_ratio,
            confidence=confidence,
            causation_type=causation_type,
        )

    def _find_related_signals(
        self,
        anomaly: PriceAnomaly,
        signals: List[MarketSignal],
    ) -> List[MarketSignal]:
        """从已有信号中查找与异动相关的信号"""
        related = []
        instrument_code = anomaly.instrument.split(".")[0]

        for sig in signals:
            # 检查信号是否影响同一股票
            instruments = [i.split(".")[0] for i in sig.affected_instruments]
            if instrument_code in instruments:
                related.append(sig)
                continue

            # 检查信号方向是否一致
            if anomaly.price_change_pct > 0 and sig.signal_direction == Direction.BULLISH:
                if self._is_time_relevant(sig, anomaly.anomaly_date):
                    related.append(sig)
            elif anomaly.price_change_pct < 0 and sig.signal_direction == Direction.BEARISH:
                if self._is_time_relevant(sig, anomaly.anomaly_date):
                    related.append(sig)

        return related[:5]

    def _is_time_relevant(self, signal: MarketSignal, anomaly_date) -> bool:
        """检查信号时间是否与异动相关（5天内）"""
        if signal.event_time is None:
            return True
        try:
            if isinstance(signal.event_time, str):
                event_dt = datetime.fromisoformat(signal.event_time.replace("Z", "+00:00"))
            else:
                event_dt = signal.event_time

            from datetime import timedelta
            delta = (anomaly_date - event_dt.date()).days if hasattr(event_dt, 'date') else abs((anomaly_date - event_dt).days)
            return delta <= 5
        except Exception:
            return True

    def _collect_targeted_news(self, anomaly: PriceAnomaly) -> List[MarketSignal]:
        """按股票代码定向采集新闻"""
        news_signals = []

        # A股：使用AKShare按股票代码采集
        if anomaly.market == Market.A_SHARE:
            try:
                from m0_collector.providers.akshare_news import AkshareNewsProvider
                code = anomaly.instrument.split(".")[0]
                provider = AkshareNewsProvider(symbol=code)
                articles = provider.fetch(limit=10)
                if articles:
                    news_signals.extend(
                        self._raw_articles_to_signals(articles, anomaly)
                    )
            except Exception as e:
                logger.warning(f"[BackwardCausation] AKShare news failed for {anomaly.instrument}: {e}")

        # 港股/美股：使用Finnhub
        if anomaly.market in (Market.HK, Market.US):
            try:
                from m0_collector.providers.finnhub_provider import FinnhubProvider
                provider = FinnhubProvider()
                if hasattr(provider, 'fetch_company_news'):
                    symbol = self._convert_to_finnhub_symbol(anomaly.instrument, anomaly.market)
                    articles = provider.fetch_company_news(symbol=symbol, limit=10)
                    if articles:
                        news_signals.extend(
                            self._raw_articles_to_signals(articles, anomaly)
                        )
            except Exception as e:
                logger.warning(f"[BackwardCausation] Finnhub news failed for {anomaly.instrument}: {e}")

        logger.info(
            f"[BackwardCausation] targeted news for {anomaly.instrument}: "
            f"{len(news_signals)} signals found"
        )
        return news_signals

    def _raw_articles_to_signals(
        self, articles, anomaly: PriceAnomaly
    ) -> List[MarketSignal]:
        """将原始新闻文章转为MarketSignal（简化版，不调用LLM）"""
        signals = []
        for article in articles[:5]:
            title = getattr(article, 'title', '') or getattr(article, 'source_name', 'Unknown')
            content = getattr(article, 'content', '') or ''
            if not content:
                content = title

            source_url = getattr(article, 'source_url', '') or ''

            direction = Direction.BULLISH if anomaly.price_change_pct > 0 else Direction.BEARISH

            sig = MarketSignal(
                signal_type=SignalType.EVENT_DRIVEN,
                signal_label=title[:80],
                description=content[:200],
                evidence_text=content[:300],
                affected_markets=[anomaly.market],
                affected_instruments=[anomaly.instrument],
                signal_direction=direction,
                event_time=datetime.now(),
                collected_time=datetime.now(),
                time_horizon=TimeHorizon.SHORT,
                intensity_score=6,
                confidence_score=5,
                timeliness_score=8,
                source_type=SourceType.NEWS,
                source_ref=source_url or "targeted_news",
                logic_frame=SignalLogicFrame(
                    what_changed=title[:60],
                    change_direction=direction,
                    affects=[anomaly.instrument],
                ),
            )
            signals.append(sig)

        return signals

    def _convert_to_finnhub_symbol(self, instrument: str, market: Market) -> str:
        """转换代码格式为Finnhub格式"""
        code = instrument.split(".")[0]
        if market == Market.HK:
            return code
        return code

    def _assess_confidence(
        self,
        anomaly: PriceAnomaly,
        causes: List[MarketSignal],
        sentiment_data: Optional[Dict],
    ) -> tuple:
        """评估溯源置信度

        Returns:
            (confidence, unexplained_ratio, causation_type)
        """
        if not causes:
            return (0.2, 1.0, "unexplained")

        # 按信号强度排序
        strong_causes = [s for s in causes if s.intensity_score >= 7]
        medium_causes = [s for s in causes if 4 <= s.intensity_score < 7]
        weak_causes = [s for s in causes if s.intensity_score < 4]

        # 评估原因对涨幅的解释比例
        cause_strength = len(strong_causes) * 3 + len(medium_causes) * 2 + len(weak_causes) * 1

        if cause_strength >= 8:
            confidence = 0.8
            unexplained_ratio = 0.1
            causation_type = self._classify_causation_type(strong_causes)
        elif cause_strength >= 4:
            confidence = 0.5
            unexplained_ratio = 0.3
            causation_type = self._classify_causation_type(strong_causes + medium_causes)
        else:
            confidence = 0.2
            unexplained_ratio = 0.6
            causation_type = "unexplained"

        # 情绪面修正
        if sentiment_data:
            fgi = sentiment_data.get("fear_greed_index", 50)
            if fgi >= 75 and anomaly.price_change_pct > 0:
                confidence *= 0.8
            elif fgi <= 25 and anomaly.price_change_pct > 0:
                confidence *= 1.1
                confidence = min(confidence, 1.0)

        return (round(confidence, 2), round(unexplained_ratio, 2), causation_type)

    def _classify_causation_type(self, causes: List[MarketSignal]) -> str:
        """从信号类型推断原因类型"""
        if not causes:
            return "unexplained"

        type_counts = {}
        for s in causes:
            t = s.signal_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        if not type_counts:
            return "unexplained"

        dominant_type = max(type_counts, key=type_counts.get)

        type_map = {
            "policy": "policy",
            "macro": "macro",
            "industry": "industry",
            "capital_flow": "capital_flow",
            "technical": "technical",
            "event_driven": "earnings",
            "sentiment": "sentiment",
            "anomalous_activity": "technical",
        }

        return type_map.get(dominant_type, "unexplained")