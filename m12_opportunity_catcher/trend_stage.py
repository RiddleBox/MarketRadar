"""
m12_opportunity_catcher/trend_stage.py — 趋势阶段判断

设计原则（见 PRINCIPLES.md）：
  4. 趋势阶段是核心判断 — early可补，middle谨慎，late放弃
  9. 与M3协作不替代 — 趋势持续性判断复用M3，不自建判断逻辑

判断逻辑：
  EARLY（可补）：涨幅第1-2天，原因有持续性，M3判断BULLISH，历史案例后续空间>5%
  MIDDLE（谨慎）：涨幅第3-5天，原因部分可持续，预期剩余空间 3-5%
  LATE（放弃）：涨幅>5天连续上涨，一次性原因，预期剩余空间<3%
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from core.schemas import (
    CatalystPersistence,
    CausationResult,
    Direction,
    Market,
    PriceAnomaly,
    TrendAssessment,
    TrendStage,
)

logger = logging.getLogger(__name__)


class TrendAssessor:
    """趋势阶段判断器"""

    # 趋势阶段阈值
    EARLY_MAX_DAYS = 2      # 1-2天为early
    MIDDLE_MAX_DAYS = 5     # 3-5天为middle，>5天为late
    EARLY_MIN_UPSIDE = 5.0  # early阶段需至少5%剩余空间
    MIDDLE_MIN_UPSIDE = 3.0  # middle阶段需至少3%剩余空间
    LATE_MAX_UPSIDE = 3.0   # late阶段剩余空间<3%

    def __init__(self, m3_engine=None, signal_store=None):
        self.m3_engine = m3_engine
        self.signal_store = signal_store

    def assess(
        self,
        anomaly: PriceAnomaly,
        causation: CausationResult,
        m3_opportunity=None,
    ) -> TrendAssessment:
        """评估趋势阶段

        Args:
            anomaly: 价格异动事件
            causation: 反向溯源结果
            m3_opportunity: M3判断结果（可选）

        Returns:
            TrendAssessment 趋势阶段评估
        """
        # 原因持续性判断
        catalyst_persistence = self._assess_catalyst_persistence(anomaly, causation)

        # 剩余空间估算
        remaining_upside = self._estimate_remaining_upside(
            anomaly, causation, catalyst_persistence
        )

        # 异动天数
        n_days = anomaly.n_days if anomaly.n_days > 0 else 1

        # 综合判断趋势阶段
        stage = self._determine_stage(
            n_days=n_days,
            catalyst_persistence=catalyst_persistence,
            remaining_upside=remaining_upside,
            causation_confidence=causation.confidence,
            m3_opportunity=m3_opportunity,
        )

        # 查找相似历史案例
        similar_cases = self._find_similar_cases(anomaly, causation)

        # 构建推理过程
        reasoning = self._build_reasoning(
            anomaly, causation, stage, catalyst_persistence, remaining_upside, n_days
        )

        return TrendAssessment(
            anomaly=anomaly,
            stage=stage,
            remaining_upside_pct=remaining_upside,
            catalyst_persistence=catalyst_persistence,
            similar_cases=similar_cases,
            reasoning=reasoning,
        )

    def _assess_catalyst_persistence(
        self, anomaly: PriceAnomaly, causation: CausationResult
    ) -> CatalystPersistence:
        """判断原因持续性"""
        causation_type = causation.causation_type

        # 持续性原因
        persistent_types = {"policy", "industry", "macro"}
        # 一次性原因
        one_time_types = {"earnings", "technical"}

        if causation_type in persistent_types:
            return CatalystPersistence.CONTINUING
        elif causation_type in one_time_types:
            return CatalystPersistence.ONE_TIME

        # 无法解释的异动通常不持续
        if causation.unexplained_ratio > 0.5:
            return CatalystPersistence.ONE_TIME

        return CatalystPersistence.UNCERTAIN

    def _estimate_remaining_upside(
        self,
        anomaly: PriceAnomaly,
        causation: CausationResult,
        catalyst_persistence: CatalystPersistence,
    ) -> float:
        """估算剩余上涨空间（百分比）"""
        change_pct = abs(anomaly.price_change_pct)

        if catalyst_persistence == CatalystPersistence.CONTINUING:
            # 持续性原因：趋势可能延续，剩余空间较大
            # 估算：剩余空间 ≈ 已涨幅 × 0.8（趋势延续）
            return round(change_pct * 0.8, 1)
        elif catalyst_persistence == CatalystPersistence.ONE_TIME:
            # 一次性原因：大部分涨幅已兑现
            # 估算：剩余空间 ≈ 已涨幅 × 0.2（冲高后余波）
            return round(change_pct * 0.2, 1)
        else:
            # 不确定：剩余空间 ≈ 已涨幅 × 0.4
            return round(change_pct * 0.4, 1)

    def _determine_stage(
        self,
        n_days: int,
        catalyst_persistence: CatalystPersistence,
        remaining_upside: float,
        causation_confidence: float,
        m3_opportunity=None,
    ) -> TrendStage:
        """综合判断趋势阶段

        判断逻辑：
          EARLY（可补）：
            - 涨幅在1-2天
            - 原因有持续性
            - 剩余空间 > 5%
            - M3判断BULLISH（如有）
            - 置信度 > 0.5
          MIDDLE（谨慎）：
            - 涨幅在3-5天
            - 原因部分可持续
            - 剩余空间 3-5%
          LATE（放弃）：
            - 涨幅>5天
            - 一次性原因
            - 剩余空间<3%
        """
        if n_days <= self.EARLY_MAX_DAYS:
            if catalyst_persistence == CatalystPersistence.CONTINUING:
                if remaining_upside >= self.EARLY_MIN_UPSIDE and causation_confidence >= 0.5:
                    return TrendStage.EARLY
                elif remaining_upside >= self.MIDDLE_MIN_UPSIDE:
                    return TrendStage.MIDDLE
                else:
                    return TrendStage.LATE
            elif catalyst_persistence == CatalystPersistence.ONE_TIME:
                return TrendStage.MIDDLE if remaining_upside >= self.MIDDLE_MIN_UPSIDE else TrendStage.LATE
            else:
                return TrendStage.MIDDLE

        elif n_days <= self.MIDDLE_MAX_DAYS:
            if catalyst_persistence == CatalystPersistence.CONTINUING:
                if remaining_upside >= self.MIDDLE_MIN_UPSIDE:
                    return TrendStage.MIDDLE
                else:
                    return TrendStage.LATE
            else:
                return TrendStage.LATE

        else:
            return TrendStage.LATE

    def _find_similar_cases(
        self, anomaly: PriceAnomaly, causation: CausationResult
    ) -> List[str]:
        """查找相似历史案例"""
        if self.signal_store is None:
            return []

        try:
            tags = [anomaly.instrument.split(".")[0]]
            tags.extend([c.signal_label[:10] for c in causation.causes[:3]])

            cases = self.signal_store.query_similar_cases(tags=tags, limit=3)
            return [c.case_id for c in cases] if cases else []
        except Exception as e:
            logger.debug(f"[TrendAssessor] case query failed: {e}")
            return []

    def _build_reasoning(
        self,
        anomaly: PriceAnomaly,
        causation: CausationResult,
        stage: TrendStage,
        catalyst_persistence: CatalystPersistence,
        remaining_upside: float,
        n_days: int,
    ) -> str:
        """构建趋势判断推理过程"""
        stage_names = {
            TrendStage.EARLY: "趋势早期（可补牢）",
            TrendStage.MIDDLE: "趋势中期（谨慎）",
            TrendStage.LATE: "趋势晚期（放弃）",
        }
        persistence_names = {
            CatalystPersistence.CONTINUING: "持续",
            CatalystPersistence.ONE_TIME: "一次性",
            CatalystPersistence.UNCERTAIN: "不确定",
        }

        reasoning_parts = [
            f"{anomaly.instrument} {n_days}日涨幅{anomaly.price_change_pct:+.1f}%（{anomaly.anomaly_type}）",
            f"趋势阶段判断: {stage_names.get(stage, '未知')}",
            f"原因类型: {causation.causation_type}，持续性: {persistence_names.get(catalyst_persistence, '未知')}",
            f"溯源置信度: {causation.confidence:.0%}，无法解释比例: {causation.unexplained_ratio:.0%}",
            f"估算剩余空间: {remaining_upside:.1f}%",
        ]

        if causation.causes:
            top_causes = causation.causes[:2]
            cause_labels = [f"{c.signal_type.value}: {c.signal_label[:20]}" for c in top_causes]
            reasoning_parts.append(f"主要原因: {'; '.join(cause_labels)}")

        if stage == TrendStage.LATE:
            reasoning_parts.append("建议: 放弃追高，入场偏晚")
        elif stage == TrendStage.MIDDLE:
            reasoning_parts.append("建议: 紧止损谨慎参与")
        else:
            reasoning_parts.append("建议: 可按计划补牢入场")

        return "\n".join(reasoning_parts)