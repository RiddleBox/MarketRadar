"""
integrations/market_sentinel.py — MarketSentinel 情绪面系统接口

MarketSentinel 是独立的情绪分析系统，产出：
  - 市场情绪指数（恐惧/贪婪/中性）
  - 主力资金流向
  - 热点板块轮动信号
  - 散户/机构情绪背离

本模块定义协议层（Protocol + 数据模型）：
  1. SentimentSignal — 情绪信号对象（与 MarketSignal 兼容）
  2. MarketSentinelAdapter — 接入适配器抽象基类
  3. MockSentinelAdapter — 测试用 Mock 实现
  4. inject_sentiment_signals() — 将情绪信号注入 M2 存储

实际 MarketSentinel 系统接入时，只需实现 MarketSentinelAdapter。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Protocol
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────

@dataclass
class SentimentReading:
    """情绪面原始读数"""

    # 整体情绪
    fear_greed_index: float        # 0=极度恐惧, 50=中性, 100=极度贪婪
    sentiment_label: str           # "extreme_fear" | "fear" | "neutral" | "greed" | "extreme_greed"
    market: str                    # "A_SHARE" | "HK" | "US"
    timestamp: datetime

    # 资金流向
    northbound_flow_1d: Optional[float] = None    # 北向资金净流入（亿元，A股）
    southbound_flow_1d: Optional[float] = None    # 南向资金净流入（亿元，港股）
    main_force_flow: Optional[float] = None       # 主力资金净流入

    # 市场结构
    up_down_ratio: Optional[float] = None         # 涨跌比（涨停/跌停）
    new_high_count: Optional[int] = None          # 创新高数量
    new_low_count: Optional[int] = None           # 创新低数量
    margin_balance: Optional[float] = None        # 融资余额（亿元）

    # 热点
    hot_sectors: List[str] = field(default_factory=list)     # 热点板块
    rotating_from: List[str] = field(default_factory=list)   # 资金流出板块
    rotating_to: List[str] = field(default_factory=list)     # 资金流入板块

    # 元数据
    source: str = "market_sentinel"
    confidence: float = 0.7


@dataclass
class SentimentSignalData:
    """
    情绪信号 — 可直接注入 M2 存储。

    结构与 MarketSignal 兼容，signal_type = "sentiment"。
    """
    signal_id: str
    signal_type: str = "sentiment"
    signal_label: str = ""
    description: str = ""
    evidence_text: str = ""
    affected_markets: List[str] = field(default_factory=list)
    affected_instruments: List[str] = field(default_factory=list)
    signal_direction: str = "NEUTRAL"  # BULLISH / BEARISH / NEUTRAL

    # 情绪专属字段
    fear_greed_index: float = 50.0
    sentiment_label: str = "neutral"
    hot_sectors: List[str] = field(default_factory=list)
    rotating_to: List[str] = field(default_factory=list)

    # 评分
    intensity_score: float = 5.0
    confidence_score: float = 7.0
    timeliness_score: float = 9.0

    event_time: Optional[datetime] = None
    collected_time: datetime = field(default_factory=datetime.now)
    source_type: str = "sentiment_system"
    source_ref: str = "market_sentinel"
    batch_id: str = ""
    time_horizon: str = "short"

    def to_market_signal_dict(self) -> dict:
        """转换为 MarketSignal 兼容的 dict，可传入 SignalStore"""
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "signal_label": self.signal_label,
            "description": self.description,
            "evidence_text": self.evidence_text,
            "affected_markets": self.affected_markets,
            "affected_instruments": self.affected_instruments,
            "signal_direction": self.signal_direction,
            "intensity_score": self.intensity_score,
            "confidence_score": self.confidence_score,
            "timeliness_score": self.timeliness_score,
            "event_time": self.event_time or self.collected_time,
            "collected_time": self.collected_time,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "batch_id": self.batch_id,
            "time_horizon": self.time_horizon,
            "logic_frame": {
                "what_changed": f"情绪面: {self.sentiment_label}",
                "change_direction": self.signal_direction,
                "affects": self.hot_sectors or self.affected_instruments,
            },
        }


# ─────────────────────────────────────────────────────────────
# 适配器抽象基类
# ─────────────────────────────────────────────────────────────

class MarketSentinelAdapter(ABC):
    """
    MarketSentinel 系统接入适配器。

    实际对接 MarketSentinel 时，继承此类并实现：
      1. fetch_reading() — 拉取当前情绪面读数
      2. to_sentiment_signals() — 转换为 SentimentSignalData 列表
    """

    @abstractmethod
    def fetch_reading(self, market: str = "A_SHARE") -> Optional[SentimentReading]:
        """
        拉取最新情绪面读数。

        Args:
            market: 目标市场

        Returns:
            SentimentReading，失败返回 None
        """
        ...

    @abstractmethod
    def to_sentiment_signals(
        self, reading: SentimentReading, batch_id: str = ""
    ) -> List[SentimentSignalData]:
        """
        将情绪读数转换为可注入 M2 的信号列表。

        转换规则由各实现自行决定，例如：
          - fear_greed < 20 → BULLISH 逆势信号（极度恐惧是买入机会）
          - 北向资金连续3日净流入 → BULLISH 信号
          - 板块轮动 → 对应板块的 BULLISH/BEARISH 信号
        """
        ...

    def fetch_and_convert(
        self, market: str = "A_SHARE", batch_id: str = ""
    ) -> List[SentimentSignalData]:
        """便捷方法：fetch + convert"""
        reading = self.fetch_reading(market)
        if reading is None:
            logger.warning(f"[MarketSentinel] 无法获取情绪读数: {market}")
            return []
        return self.to_sentiment_signals(reading, batch_id=batch_id)


# ─────────────────────────────────────────────────────────────
# Mock 实现（测试 / 开发用）
# ─────────────────────────────────────────────────────────────

class MockSentinelAdapter(MarketSentinelAdapter):
    """
    测试用 Mock 实现，返回固定的情绪读数。
    """

    def __init__(self, fear_greed: float = 35.0, northbound: float = 50.0):
        self.fear_greed = fear_greed
        self.northbound = northbound

    def fetch_reading(self, market: str = "A_SHARE") -> Optional[SentimentReading]:
        fg = self.fear_greed
        if fg <= 20:
            label = "extreme_fear"
        elif fg <= 40:
            label = "fear"
        elif fg <= 60:
            label = "neutral"
        elif fg <= 80:
            label = "greed"
        else:
            label = "extreme_greed"

        return SentimentReading(
            fear_greed_index=fg,
            sentiment_label=label,
            market=market,
            timestamp=datetime.now(),
            northbound_flow_1d=self.northbound,
            main_force_flow=self.northbound * 0.6,
            up_down_ratio=1.8,
            hot_sectors=["新能源", "半导体", "医药"],
            rotating_to=["新能源", "半导体"],
            rotating_from=["消费", "地产"],
        )

    def to_sentiment_signals(
        self, reading: SentimentReading, batch_id: str = ""
    ) -> List[SentimentSignalData]:
        import uuid
        signals = []
        now = datetime.now()

        # 信号1：恐惧贪婪指数
        fg = reading.fear_greed_index
        if fg <= 25:
            direction, intensity, label = "BULLISH", 8.0, f"极度恐惧区间（FGI={fg:.0f}）逆势做多机会"
        elif fg >= 75:
            direction, intensity, label = "BEARISH", 7.0, f"极度贪婪区间（FGI={fg:.0f}）警惕回调"
        else:
            direction, intensity, label = "NEUTRAL", 4.0, f"情绪中性（FGI={fg:.0f}）"

        signals.append(SentimentSignalData(
            signal_id=f"sent_{uuid.uuid4().hex[:8]}",
            signal_label=label,
            description=f"恐惧贪婪指数 {fg:.0f}（{reading.sentiment_label}）。市场情绪处于 {reading.sentiment_label} 区间。",
            evidence_text=f"FGI={fg:.0f}, 北向资金={reading.northbound_flow_1d}亿, 涨跌比={reading.up_down_ratio}",
            affected_markets=[reading.market],
            affected_instruments=[],
            signal_direction=direction,
            fear_greed_index=fg,
            sentiment_label=reading.sentiment_label,
            hot_sectors=reading.hot_sectors,
            rotating_to=reading.rotating_to,
            intensity_score=intensity,
            confidence_score=7.5,
            timeliness_score=9.5,
            event_time=reading.timestamp,
            batch_id=batch_id,
            time_horizon="short",
        ))

        # 信号2：北向资金（A股专有）
        if reading.market == "A_SHARE" and reading.northbound_flow_1d is not None:
            nf = reading.northbound_flow_1d
            if nf > 100:
                direction, intensity = "BULLISH", 7.0
                label = f"北向资金大幅净流入 +{nf:.0f}亿，外资看多情绪明确"
            elif nf < -100:
                direction, intensity = "BEARISH", 7.0
                label = f"北向资金大幅净流出 {nf:.0f}亿，外资看空"
            else:
                direction, intensity = "NEUTRAL", 3.0
                label = f"北向资金小幅变动（{nf:+.0f}亿），无明显倾向"

            signals.append(SentimentSignalData(
                signal_id=f"sent_{uuid.uuid4().hex[:8]}",
                signal_label=label,
                description=label,
                evidence_text=f"北向资金单日净流入: {nf:+.1f}亿元",
                affected_markets=[reading.market],
                signal_direction=direction,
                fear_greed_index=fg,
                sentiment_label=reading.sentiment_label,
                intensity_score=intensity,
                confidence_score=8.0,
                timeliness_score=9.0,
                event_time=reading.timestamp,
                batch_id=batch_id,
                time_horizon="short",
            ))

        # 信号3：板块轮动
        if reading.rotating_to:
            signals.append(SentimentSignalData(
                signal_id=f"sent_{uuid.uuid4().hex[:8]}",
                signal_label=f"板块轮动：资金流入 {'/'.join(reading.rotating_to[:2])}",
                description=f"板块轮动信号：资金从 {reading.rotating_from} 流向 {reading.rotating_to}",
                evidence_text=f"热点板块: {reading.hot_sectors}，轮入: {reading.rotating_to}，轮出: {reading.rotating_from}",
                affected_markets=[reading.market],
                affected_instruments=reading.rotating_to,
                signal_direction="BULLISH",
                fear_greed_index=fg,
                sentiment_label=reading.sentiment_label,
                hot_sectors=reading.hot_sectors,
                rotating_to=reading.rotating_to,
                intensity_score=6.0,
                confidence_score=6.5,
                timeliness_score=8.5,
                event_time=reading.timestamp,
                batch_id=batch_id,
                time_horizon="short",
            ))

        return signals


# ─────────────────────────────────────────────────────────────
# 注入函数：情绪信号 → M2 存储
# ─────────────────────────────────────────────────────────────

def inject_sentiment_signals(
    adapter: MarketSentinelAdapter,
    markets: List[str] = None,
    batch_id: str = "",
) -> List[SentimentSignalData]:
    """
    从 MarketSentinel 拉取情绪信号并注入 M2 存储。

    Args:
        adapter:  MarketSentinelAdapter 实例
        markets:  目标市场列表，默认 ["A_SHARE", "HK"]
        batch_id: 批次标识

    Returns:
        注入的 SentimentSignalData 列表
    """
    from m2_storage.signal_store import SignalStore
    from core.schemas import MarketSignal

    markets = markets or ["A_SHARE", "HK"]
    if not batch_id:
        batch_id = f"sentinel_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    all_signals = []
    for market in markets:
        signals = adapter.fetch_and_convert(market=market, batch_id=batch_id)
        all_signals.extend(signals)
        logger.info(f"[MarketSentinel] {market}: {len(signals)} 条情绪信号")

    if not all_signals:
        logger.warning("[MarketSentinel] 无情绪信号产出")
        return []

    # 转换为 MarketSignal 并存入 M2
    store = SignalStore()
    market_signals = []
    for s in all_signals:
        try:
            ms = MarketSignal(**s.to_market_signal_dict())
            market_signals.append(ms)
        except Exception as e:
            logger.error(f"[MarketSentinel] 信号转换失败: {e}")

    if market_signals:
        store.save(market_signals)
        logger.info(f"[MarketSentinel] 注入 {len(market_signals)} 条情绪信号到 M2")

    return all_signals
