"""
m3_judgment/implicit_signal_adapter.py - 隐性信号适配器

职责: 将M1.5的ImplicitSignal转换为M3可以理解的MarketSignal格式

Phase 3.5架构修正的关键组件
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime
from typing import List

from core.schemas import MarketSignal, Direction, Market, SignalType, TimeHorizon, SourceType, SignalLogicFrame
from m1_5_implicit_reasoner.models import ImplicitSignal

logger = logging.getLogger(__name__)


class ImplicitSignalAdapter:
    """隐性信号适配器

    将ImplicitSignal转换为MarketSignal，使M3能够处理隐性信号
    """

    @staticmethod
    def to_market_signal(implicit_signal: ImplicitSignal) -> MarketSignal:
        """
        将ImplicitSignal转换为MarketSignal

        映射规则:
        - signal_id → signal_id (保持追溯)
        - signal_type → signal_type
        - opportunity_description → description
        - target_symbols → affected_instruments
        - prior_confidence → confidence_score (转为1-10分)
        - industry_sector → signal_label
        - reasoning_chain → 提取为tags

        Args:
            implicit_signal: M1.5生成的隐性信号

        Returns:
            MarketSignal对象
        """
        # 推断信号类型
        signal_type = ImplicitSignalAdapter._map_signal_type(implicit_signal.signal_type)

        # 推断时间窗口
        time_horizon = ImplicitSignalAdapter._map_time_horizon(
            implicit_signal.expected_impact_timeframe
        )

        # 推断市场
        markets = ImplicitSignalAdapter._infer_markets(implicit_signal.target_symbols)

        # 置信度转换 (0.0-1.0 → 1-10分)
        confidence_score = int(implicit_signal.prior_confidence * 10)

        # 构建tags
        tags = [
            f"sector:{implicit_signal.industry_sector}",
            f"timeframe:{implicit_signal.expected_impact_timeframe}",
            f"source:{implicit_signal.reasoning_chain.source_event[:50] if implicit_signal.reasoning_chain else 'unknown'}",
            "implicit_signal",  # 标记为隐性信号
        ]

        # 提取推理链关键信息
        if implicit_signal.reasoning_chain:
            chain = implicit_signal.reasoning_chain
            tags.append(f"causal_links:{len(chain.causal_links)}")

            # 添加关键因果关系
            for link in chain.causal_links[:3]:  # 最多3个
                tags.append(f"relation:{link.relation_type}")

        # 从source_info提取来源信息
        source_type = SourceType.NEWS  # 默认新闻来源
        source_ref = "M1.5隐性推理"
        evidence_text = implicit_signal.opportunity_description

        if implicit_signal.source_info:
            # 尝试从source_info提取更详细的来源信息
            if "title" in implicit_signal.source_info:
                source_ref = implicit_signal.source_info["title"]
            if "content" in implicit_signal.source_info:
                evidence_text = implicit_signal.source_info["content"][:500]  # 截取前500字符

        # 构建logic_frame
        logic_frame = SignalLogicFrame(
            what_changed=implicit_signal.reasoning_chain.source_event if implicit_signal.reasoning_chain else "隐性机会识别",
            change_direction=Direction.BULLISH,
            affects=[implicit_signal.industry_sector] + implicit_signal.target_symbols[:3]
        )

        # 构建MarketSignal
        market_signal = MarketSignal(
            signal_id=implicit_signal.signal_id,
            signal_type=signal_type,
            signal_label=implicit_signal.industry_sector,
            description=implicit_signal.opportunity_description,
            evidence_text=evidence_text,
            signal_direction=Direction.BULLISH,  # 隐性信号通常是利好机会
            affected_markets=markets,
            affected_instruments=implicit_signal.target_symbols,
            event_time=implicit_signal.created_at,
            collected_time=implicit_signal.created_at,
            time_horizon=time_horizon,
            intensity_score=confidence_score,  # 使用置信度作为强度
            confidence_score=confidence_score,
            timeliness_score=ImplicitSignalAdapter._calculate_timeliness(
                implicit_signal.expected_impact_timeframe
            ),
            source_type=source_type,
            source_ref=source_ref,
            logic_frame=logic_frame,
            tags=tags,
            metadata={
                "reasoning_chain": asdict(implicit_signal.reasoning_chain) if implicit_signal.reasoning_chain else {},
                "prior_confidence": implicit_signal.prior_confidence,
                "source_event": implicit_signal.reasoning_chain.source_event if implicit_signal.reasoning_chain else "unknown",
                "source_info": implicit_signal.source_info,
            }
        )

        logger.debug(
            f"[ImplicitAdapter] 转换信号 {implicit_signal.signal_id}: "
            f"{implicit_signal.industry_sector} → {signal_type.value}"
        )

        return market_signal

    @staticmethod
    def to_market_signals_batch(implicit_signals: List[ImplicitSignal]) -> List[MarketSignal]:
        """批量转换隐性信号

        Args:
            implicit_signals: ImplicitSignal列表

        Returns:
            MarketSignal列表
        """
        market_signals = []
        for sig in implicit_signals:
            try:
                market_signal = ImplicitSignalAdapter.to_market_signal(sig)
                market_signals.append(market_signal)
            except Exception as e:
                logger.error(f"[ImplicitAdapter] 转换失败 {sig.signal_id}: {e}")

        logger.info(
            f"[ImplicitAdapter] 批量转换 {len(market_signals)}/{len(implicit_signals)} 个信号"
        )
        return market_signals

    @staticmethod
    def _map_signal_type(implicit_type: str) -> SignalType:
        """映射信号类型

        隐性信号类型 → MarketSignal类型
        """
        type_mapping = {
            "policy_driven": SignalType.POLICY,
            "tech_breakthrough": SignalType.INDUSTRY,
            "diplomatic_event": SignalType.EVENT_DRIVEN,
            "social_trend": SignalType.INDUSTRY,
            "supply_chain": SignalType.INDUSTRY,
            "regulatory_change": SignalType.POLICY,
        }

        return type_mapping.get(implicit_type, SignalType.EVENT_DRIVEN)

    @staticmethod
    def _map_time_horizon(timeframe: str) -> TimeHorizon:
        """映射时间框架

        隐性信号时间框架 → MarketSignal时间窗口
        """
        horizon_mapping = {
            "immediate": TimeHorizon.SHORT,
            "short_term": TimeHorizon.SHORT,
            "mid_term": TimeHorizon.MEDIUM,
            "long_term": TimeHorizon.LONG,
        }

        return horizon_mapping.get(timeframe, TimeHorizon.MEDIUM)

    @staticmethod
    def _infer_markets(symbols: List[str]) -> List[Market]:
        """从标的代码推断市场

        Args:
            symbols: 标的代码列表

        Returns:
            Market列表
        """
        markets = set()

        for symbol in symbols:
            if symbol.endswith(".SH") or symbol.endswith(".SZ"):
                markets.add(Market.A_SHARE)
            elif symbol.endswith(".HK"):
                markets.add(Market.HK)
            elif "." not in symbol or symbol.endswith(".US"):
                markets.add(Market.US)

        return list(markets) if markets else [Market.A_SHARE]

    @staticmethod
    def _calculate_timeliness(timeframe: str) -> int:
        """计算时效性分数

        时间框架越短，时效性越高

        Args:
            timeframe: 时间框架

        Returns:
            时效性分数 (1-10)
        """
        timeliness_map = {
            "immediate": 10,
            "short_term": 8,
            "mid_term": 6,
            "long_term": 4,
        }

        return timeliness_map.get(timeframe, 5)


# 便捷函数
def convert_implicit_to_market(implicit_signal: ImplicitSignal) -> MarketSignal:
    """便捷函数: 转换单个隐性信号"""
    return ImplicitSignalAdapter.to_market_signal(implicit_signal)


def convert_implicit_to_market_batch(implicit_signals: List[ImplicitSignal]) -> List[MarketSignal]:
    """便捷函数: 批量转换隐性信号"""
    return ImplicitSignalAdapter.to_market_signals_batch(implicit_signals)
