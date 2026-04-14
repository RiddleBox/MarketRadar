"""
m3_judgment/sentiment_resonance.py — 情绪共振增强器

基于 M10 最新情绪快照，对 M3 产出的 OpportunityObject 做轻量后处理：
- 情绪与交易方向同向且处于极值/强趋势 → 提升 execution_readiness，必要时抬升 priority
- 情绪与交易方向反向且处于极值 → 降低 execution_readiness，并添加 warning

设计原则：
- 不改动 M3 的机会识别主逻辑，仅做后处理增强
- 默认静默失败：没有情绪快照时直接返回原对象
- 不依赖实时网络，只读取本地 latest snapshot 文件
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.schemas import Direction, OpportunityObject, PriorityLevel

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
LATEST_SNAPSHOT = ROOT / "data" / "sentiment" / "latest.json"


@dataclass
class SentimentContext:
    fear_greed_score: float
    sentiment_label: str
    direction: str
    trend_is_rising: Optional[bool] = None

    @property
    def is_extreme_greed(self) -> bool:
        return self.fear_greed_score >= 75

    @property
    def is_extreme_fear(self) -> bool:
        return self.fear_greed_score <= 25

    @property
    def is_extreme(self) -> bool:
        return self.is_extreme_greed or self.is_extreme_fear


class SentimentResonanceEnhancer:
    def __init__(self, snapshot_path: Optional[Path] = None):
        self.snapshot_path = snapshot_path or LATEST_SNAPSHOT

    def load_latest_context(self) -> Optional[SentimentContext]:
        if not self.snapshot_path.exists():
            return None
        try:
            data = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            return SentimentContext(
                fear_greed_score=float(data.get("fear_greed_score", data.get("fear_greed", 50.0))),
                sentiment_label=str(data.get("sentiment_label", "unknown")),
                direction=str(data.get("direction", "NEUTRAL")).upper(),
                trend_is_rising=data.get("trend_is_rising"),
            )
        except Exception as e:
            logger.warning(f"[M3 Resonance] 读取情绪快照失败: {e}")
            return None

    def enhance(self, opp: OpportunityObject, ctx: Optional[SentimentContext] = None) -> OpportunityObject:
        ctx = ctx or self.load_latest_context()
        if ctx is None:
            return opp

        warnings = list(opp.warnings or [])
        score = opp.opportunity_score.model_copy(deep=True)
        priority = opp.priority_level
        direction = opp.trade_direction

        aligned_bull = direction == Direction.BULLISH and ctx.direction == "BULLISH"
        aligned_bear = direction == Direction.BEARISH and ctx.direction == "BEARISH"
        contrarian_bull = direction == Direction.BULLISH and ctx.is_extreme_fear
        contrarian_bear = direction == Direction.BEARISH and ctx.is_extreme_greed
        opposed_bull = direction == Direction.BULLISH and ctx.is_extreme_greed is False and ctx.direction == "BEARISH"
        opposed_bear = direction == Direction.BEARISH and ctx.is_extreme_fear is False and ctx.direction == "BULLISH"

        if aligned_bull and ctx.fear_greed_score >= 60:
            score.execution_readiness = min(1.0, round(score.execution_readiness + 0.12, 2))
            score.market_confirmation = min(10, score.market_confirmation + 1)
            warnings.append(f"情绪共振增强：市场情绪偏多（FG={ctx.fear_greed_score:.1f}）")
            if priority in (PriorityLevel.WATCH, PriorityLevel.RESEARCH):
                priority = PriorityLevel.POSITION

        elif aligned_bear and ctx.fear_greed_score <= 40:
            score.execution_readiness = min(1.0, round(score.execution_readiness + 0.12, 2))
            score.market_confirmation = min(10, score.market_confirmation + 1)
            warnings.append(f"情绪共振增强：市场情绪偏空（FG={ctx.fear_greed_score:.1f}）")
            if priority in (PriorityLevel.WATCH, PriorityLevel.RESEARCH):
                priority = PriorityLevel.POSITION

        elif contrarian_bull:
            score.execution_readiness = min(1.0, round(score.execution_readiness + 0.08, 2))
            score.consensus_gap = min(10, score.consensus_gap + 1)
            warnings.append(f"逆向机会增强：市场处于极端恐惧（FG={ctx.fear_greed_score:.1f}）")

        elif contrarian_bear:
            score.execution_readiness = min(1.0, round(score.execution_readiness + 0.08, 2))
            score.consensus_gap = min(10, score.consensus_gap + 1)
            warnings.append(f"逆向机会增强：市场处于极端贪婪（FG={ctx.fear_greed_score:.1f}）")

        elif opposed_bull or opposed_bear:
            score.execution_readiness = max(0.0, round(score.execution_readiness - 0.12, 2))
            warnings.append(
                f"情绪背离：当前机会方向与市场情绪相反（FG={ctx.fear_greed_score:.1f}, sentiment={ctx.direction}）"
            )

        return opp.model_copy(update={
            "priority_level": priority,
            "opportunity_score": score,
            "warnings": warnings,
        })
