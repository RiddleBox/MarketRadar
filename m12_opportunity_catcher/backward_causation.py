"""
m12_opportunity_catcher/backward_causation.py — 反向溯源

设计原则（见 PRINCIPLES.md）：
  2. 溯因必须有证据 — 每次补牢必须连到明确原因
  找不到原因的异动 = 放弃，无因追高 = 赌博

反向溯源流程：
  1. M0定向采集：按股票代码采集相关新闻
  2. M1解码：对采集到的新闻运行SignalDecoder（LLM提取结构化信号）
  3. M10情绪：获取恐贪指数作为背景
  4. M2查询：从SignalStore检索已有相关信号
  5. 溯源置信度评估：基于M1解码信号的强度/置信度，非硬编码
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
    """反向溯源器

    编排 M0→M1→M2 子链路：
    - M0 定向采集新闻（按股票代码）
    - M1 LLM解码为结构化信号（SignalDecoder）
    - M2 查询已有相关信号
    如果M0/M1不可用，降级到新闻标题关键词匹配。
    """

    CAUSATION_TYPE_MAP = {
        "policy": SignalType.POLICY,
        "industry": SignalType.INDUSTRY,
        "earnings": SignalType.EVENT_DRIVEN,
        "capital_flow": SignalType.CAPITAL_FLOW,
        "technical": SignalType.TECHNICAL,
        "macro": SignalType.MACRO,
    }

    def __init__(self, llm_client=None, news_providers: dict = None,
                 signal_decoder=None, signal_store=None):
        self.llm_client = llm_client
        self.news_providers = news_providers or {}
        self.signal_decoder = signal_decoder
        self.signal_store = signal_store

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

        # Step 1: 从M2历史信号中查找相关信号
        if historical_signals:
            rel_signals = self._find_related_signals(anomaly, historical_signals)
            causes.extend(rel_signals)

        # Step 2: M0定向采集 + M1解码（核心溯源）
        news_signals = self._collect_and_decode_news(anomaly)
        causes.extend(news_signals)

        # Step 3: 从M2 SignalStore查询补充（如果有signal_store）
        if self.signal_store and len(causes) < 3:
            store_signals = self._query_signal_store(anomaly)
            causes.extend(store_signals)

        # Step 4: 评估溯源置信度
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
            instruments = [i.split(".")[0] for i in sig.affected_instruments]
            if instrument_code in instruments:
                related.append(sig)
                continue

            if anomaly.price_change_pct > 0 and sig.signal_direction == Direction.BULLISH:
                if self._is_time_relevant(sig, anomaly.anomaly_date):
                    related.append(sig)
            elif anomaly.price_change_pct < 0 and sig.signal_direction == Direction.BEARISH:
                if self._is_time_relevant(sig, anomaly.anomaly_date):
                    related.append(sig)

        return related[:5]

    def _collect_and_decode_news(self, anomaly: PriceAnomaly) -> List[MarketSignal]:
        """M0定向采集 → M1解码：获取新闻并用LLM提取结构化信号。

        优先使用M1 SignalDecoder做LLM解码。
        如果LLM不可用，降级到关键词匹配的简化信号。
        """
        raw_articles = []

        # A股：AKShare按股票代码采集
        if anomaly.market == Market.A_SHARE:
            try:
                from m0_collector.providers.akshare_news import AkshareNewsProvider
                code = anomaly.instrument.split(".")[0]
                provider = AkshareNewsProvider(symbol=code)
                articles = provider.fetch(limit=10)
                if articles:
                    raw_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[BackwardCausation] AKShare news failed for {anomaly.instrument}: {e}")

        # 港股/美股：Finnhub
        if anomaly.market in (Market.HK, Market.US):
            try:
                from m0_collector.providers.finnhub_provider import FinnhubProvider
                provider = FinnhubProvider()
                if hasattr(provider, 'fetch_company_news'):
                    symbol = self._convert_to_finnhub_symbol(anomaly.instrument, anomaly.market)
                    articles = provider.fetch_company_news(symbol=symbol, limit=10)
                    if articles:
                        raw_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[BackwardCausation] Finnhub news failed for {anomaly.instrument}: {e}")

        if not raw_articles:
            logger.info(f"[BackwardCausation] No news articles found for {anomaly.instrument}")
            return []

        # M1 LLM解码
        decoded_signals = self._decode_articles_with_m1(raw_articles, anomaly)
        if decoded_signals:
            logger.info(
                f"[BackwardCausation] M1 decoded {len(decoded_signals)} signals "
                f"from {len(raw_articles)} articles for {anomaly.instrument}"
            )
            return decoded_signals

        # 降级：简化信号（无LLM时）
        logger.warning(f"[BackwardCausation] M1 unavailable, using simplified signals for {anomaly.instrument}")
        return self._fallback_simple_signals(raw_articles, anomaly)

    def _decode_articles_with_m1(
        self, articles, anomaly: PriceAnomaly
    ) -> List[MarketSignal]:
        """用M1 SignalDecoder解码新闻文章为结构化信号。

        每篇文章单独调用M1解码，合并去重。
        """
        if self.signal_decoder is None:
            try:
                from m1_decoder.decoder import SignalDecoder
                self.signal_decoder = SignalDecoder(llm_client=self.llm_client)
            except Exception as e:
                logger.warning(f"[BackwardCausation] Cannot init SignalDecoder: {e}")
                return []

        all_signals = []
        batch_id = f"m12_{anomaly.instrument}_{anomaly.anomaly_date.isoformat()}"

        for article in articles[:5]:
            title = getattr(article, 'title', '') or ''
            content = getattr(article, 'content', '') or ''
            source_url = getattr(article, 'source_url', '') or ''

            raw_text = f"{title}\n\n{content}" if content else title
            if len(raw_text) < 20:
                continue

            try:
                signals = self.signal_decoder.decode(
                    raw_text=raw_text,
                    source_ref=source_url or f"m12_targeted_{anomaly.instrument}",
                    source_type=SourceType.NEWS,
                    batch_id=batch_id,
                )

                # 过滤只保留与异动股票相关的信号
                instrument_code = anomaly.instrument.split(".")[0]
                relevant = []
                for sig in signals:
                    sig_instruments = [i.split(".")[0] for i in sig.affected_instruments]
                    if instrument_code in sig_instruments or sig.signal_type in (
                        SignalType.POLICY, SignalType.INDUSTRY, SignalType.MACRO,
                    ):
                        relevant.append(sig)

                all_signals.extend(relevant)
            except Exception as e:
                logger.debug(f"[BackwardCausation] M1 decode failed for article: {e}")
                continue

        # 去重
        seen_labels = set()
        unique = []
        for sig in all_signals:
            if sig.signal_label not in seen_labels:
                seen_labels.add(sig.signal_label)
                unique.append(sig)

        return unique[:10]

    def _fallback_simple_signals(
        self, articles, anomaly: PriceAnomaly
    ) -> List[MarketSignal]:
        """降级模式：无LLM时，从新闻标题生成简化信号。

        信号的质量（intensity/confidence）设为中等偏低，
        因为未经LLM深度分析，只能作为弱证据。
        """
        signals = []
        direction = Direction.BULLISH if anomaly.price_change_pct > 0 else Direction.BEARISH

        for article in articles[:3]:
            title = getattr(article, 'title', '') or getattr(article, 'source_name', 'Unknown')
            content = getattr(article, 'content', '') or ''
            if not content:
                content = title
            source_url = getattr(article, 'source_url', '') or ''

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
                intensity_score=5,
                confidence_score=4,
                timeliness_score=7,
                source_type=SourceType.NEWS,
                source_ref=source_url or "m12_targeted_fallback",
                logic_frame=SignalLogicFrame(
                    what_changed=title[:60],
                    change_direction=direction,
                    affects=[anomaly.instrument],
                ),
            )
            signals.append(sig)

        return signals

    def _query_signal_store(self, anomaly: PriceAnomaly) -> List[MarketSignal]:
        """从M2 SignalStore查询与异动股票相关的近期信号。"""
        try:
            from datetime import timedelta
            lookback = anomaly.anomaly_date - timedelta(days=5)
            signals = self.signal_store.get_by_time_range(
                start=lookback,
                end=anomaly.anomaly_date,
                markets=[anomaly.market],
            )
            instrument_code = anomaly.instrument.split(".")[0]
            related = []
            for sig in signals:
                sig_codes = [i.split(".")[0] for i in sig.affected_instruments]
                if instrument_code in sig_codes:
                    related.append(sig)
            return related[:5]
        except Exception as e:
            logger.debug(f"[BackwardCausation] SignalStore query failed: {e}")
            return []

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

        基于M1解码信号的intensity_score和confidence_score，
        而非硬编码打分。没有LLM解码的降级信号得分偏低。
        """
        if not causes:
            return (0.2, 1.0, "unexplained")

        # 区分LLM解码的信号（高质量）和降级信号（低质量）
        high_quality = [s for s in causes if s.confidence_score >= 6 and s.intensity_score >= 6]
        medium_quality = [s for s in causes if s.confidence_score >= 4 and s.intensity_score >= 4]
        low_quality = [s for s in causes if s.confidence_score < 4 or s.intensity_score < 4]

        # 加权评分：高质量3分，中等2分，低质量1分
        cause_strength = len(high_quality) * 3 + len(medium_quality) * 2 + len(low_quality) * 1

        # 方向一致性加权：信号方向与异动方向一致则加成
        anomaly_direction = Direction.BULLISH if anomaly.price_change_pct > 0 else Direction.BEARISH
        direction_bonus = sum(
            1 for s in causes
            if s.signal_direction == anomaly_direction
        )

        cause_strength += direction_bonus

        if cause_strength >= 8:
            confidence = 0.8
            unexplained_ratio = 0.1
            causation_type = self._classify_causation_type(high_quality or medium_quality or low_quality)
        elif cause_strength >= 4:
            confidence = 0.5
            unexplained_ratio = 0.3
            causation_type = self._classify_causation_type(medium_quality or low_quality)
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