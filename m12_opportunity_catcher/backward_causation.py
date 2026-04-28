"""
m12_opportunity_catcher/backward_causation.py — 反向溯源

设计原则（见 PRINCIPLES.md）：
  M12 只负责"找原因"，不做任何判断。
  溯因必须有证据 — 找到相关信号后，信号列表交给 M3 判断。
  无因 = 放弃（不追高）。

流程：
  1. M0 定向采集：按股票代码采集相关新闻
  2. M1 解码：用 SignalDecoder（LLM）解码为结构化信号
  3. M2 查询：补充已有相关历史信号
  4. 输出：信号列表 + 原因类型判断（有因/无因）
  
  置信度、优先级、是否构成机会 → 全部交给 M3 judge()
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

    只做三件事：
    1. 从M2找已有相关信号
    2. M0定向采集+M1解码（LLM提取结构化信号）
    3. 原因分类（有因/无因）

    不做：置信度打分、机会判断 → 这些交给M3
    """

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
        """反向溯源：找原因，不判断。

        Args:
            anomaly: 价格异动事件
            historical_signals: M2中近期相关信号
            sentiment_data: M10情绪数据（仅用于元数据，不做判断）

        Returns:
            CausationResult — causes列表 + 原因类型
            置信度字段仅表示"有因程度"：有因=True, 无因=False
        """
        causes = []

        # Step 1: 从M2历史信号中查找相关信号
        if historical_signals:
            rel_signals = self._find_related_signals(anomaly, historical_signals)
            causes.extend(rel_signals)

        # Step 2: M0定向采集 + M1解码
        news_signals = self._collect_and_decode_news(anomaly)
        causes.extend(news_signals)

        # Step 3: 从M2 SignalStore查询补充
        if self.signal_store and len(causes) < 3:
            store_signals = self._query_signal_store(anomaly)
            causes.extend(store_signals)

        # 去重
        causes = self._deduplicate_signals(causes)

        # Step 4: 原因分类（只分类，不打分）
        causation_type = self._classify_causation_type(causes)

        # Step 5: 有因/无因（binary）
        has_cause = len(causes) > 0 and causation_type != "unexplained"
        # confidence 只表示"有没有找到原因"：
        #   有因 = 1.0（交给M3去量化）
        #   无因 = 0.0（放弃，不追高）
        confidence = 1.0 if has_cause else 0.0
        unexplained_ratio = 0.0 if has_cause else 1.0

        return CausationResult(
            anomaly=anomaly,
            causes=causes,
            unexplained_ratio=unexplained_ratio,
            confidence=confidence,
            causation_type=causation_type,
        )

    # ── 信号去重 ──────────────────────────────────────────────

    @staticmethod
    def _deduplicate_signals(signals: List[MarketSignal]) -> List[MarketSignal]:
        seen = set()
        unique = []
        for sig in signals:
            key = (sig.signal_label[:40], sig.signal_type.value)
            if key not in seen:
                seen.add(key)
                unique.append(sig)
        return unique

    # ── M2 相关信号查找 ────────────────────────────────────────

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

    # ── M0 采集 + M1 解码 ──────────────────────────────────

    def _collect_and_decode_news(self, anomaly: PriceAnomaly) -> List[MarketSignal]:
        """M0定向采集 → M1解码：获取新闻并用LLM提取结构化信号。"""
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

        # 降级：无LLM时生成简化信号（弱证据）
        logger.warning(f"[BackwardCausation] M1 unavailable, using simplified signals for {anomaly.instrument}")
        return self._fallback_simple_signals(raw_articles, anomaly)

    def _decode_articles_with_m1(
        self, articles, anomaly: PriceAnomaly
    ) -> List[MarketSignal]:
        """用M1 SignalDecoder解码新闻文章为结构化信号。"""
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

        return all_signals[:10]

    def _fallback_simple_signals(
        self, articles, anomaly: PriceAnomaly
    ) -> List[MarketSignal]:
        """降级模式：无LLM时，从新闻标题生成简化信号（弱证据）。"""
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

    # ── 工具方法 ────────────────────────────────────────────────

    @staticmethod
    def _is_time_relevant(signal: MarketSignal, anomaly_date) -> bool:
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

    @staticmethod
    def _convert_to_finnhub_symbol(instrument: str, market: Market) -> str:
        code = instrument.split(".")[0]
        if market == Market.HK:
            return code
        return code

    @staticmethod
    def _classify_causation_type(causes: List[MarketSignal]) -> str:
        """从信号类型推断原因类型（只分类，不打分）。"""
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