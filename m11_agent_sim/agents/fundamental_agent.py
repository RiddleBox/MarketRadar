"""
m11_agent_sim/agents/fundamental_agent.py — 基本面型 Agent

角色定位：
  以基本面估值为锚的价值投资者。看重个股/指数的估值水平、
  盈利质量和行业景气度，对短期情绪波动不敏感。

数据来源：东财综合评分（composite_score，0~100）
行为特征：
  - 综合评分高 + 情绪低迷（FG<40）→ 低估区间，看多（逆向价值）
  - 综合评分低 + 情绪高涨（FG>70）→ 高估区间，看空（价值泡沫）
  - 中间区间 → 中性，等待更明确信号
  - 对上游情绪类信号不敏感，权重低
"""
from __future__ import annotations

import math
from typing import List

from ..base_agent import BaseMarketAgent
from ..schemas import AgentOutput, MarketInput


class FundamentalAgent(BaseMarketAgent):
    """基本面型 Agent"""

    agent_type = "fundamental"
    default_weight = 0.15   # 短期模拟中权重偏低，基本面是慢变量

    def _build_system_prompt(self) -> str:
        return (
            "你是一个价值投资者，专注于基本面估值。"
            "你判断市场是否处于低估/高估区间，给出中长期方向判断。"
            "你对短期情绪波动不敏感，但会在情绪极值时逆向操作。"
            "只输出 JSON，格式：\n"
            '{"direction": "BULLISH|BEARISH|NEUTRAL", '
            '"bullish_prob": 0.0~1.0, "bearish_prob": 0.0~1.0, "neutral_prob": 0.0~1.0, '
            '"confidence": 0.0~1.0, "intensity": 0.0~10.0, "reasoning": "简要推理（50字内）"}'
        )

    def _build_prompt(self, market_input: MarketInput, upstream_context) -> str:
        sent = market_input.sentiment
        p = market_input.price
        consensus = self.upstream_consensus(upstream_context)
        lines = [
            f"市场：{market_input.market}  日期：{market_input.timestamp.strftime('%Y-%m-%d')}",
            "",
            "【基本面数据】",
            f"  东财综合评分均值：（需从外部注入，当前使用涨跌比代理）",
            f"  涨跌比：{sent.advance_decline_ratio:.1%}（反映市场整体健康度）",
            f"  20日涨跌：{p.price_20d_chg_pct:+.2%}",
            "",
            "【情绪面（逆向参考）】",
            f"  恐贪指数：{sent.fear_greed_index:.1f} — 极值时给出逆向判断",
            "",
            "【上游共识（我会适当忽略）】",
            f"  {consensus['direction']} 置信{consensus['avg_confidence']:.0%}",
            "\n请从基本面/估值角度给出判断：",
        ]
        return "\n".join(lines)

    def _analyze_rule_based(
        self, market_input: MarketInput, upstream_context: List[AgentOutput]
    ) -> AgentOutput:
        fg = market_input.sentiment.fear_greed_index
        adr = market_input.sentiment.advance_decline_ratio
        p20 = market_input.price.price_20d_chg_pct

        # 基本面得分（用可用数据代理）
        # 涨跌比作为市场广度代理
        breadth_score = adr * 100   # 0~100

        # 估值逻辑：情绪极低 + 基本面稳 → 低估区，看多
        # 情绪极高 + 涨幅已大 → 高估区，看空
        valuation_bias = 0.0

        if fg < 20:
            # 极度恐惧：价值投资者认为低估
            valuation_bias = +2.0
        elif fg < 35:
            valuation_bias = +1.0
        elif fg > 80:
            # 极度贪婪：价值投资者认为高估
            valuation_bias = -2.0
        elif fg > 65:
            valuation_bias = -1.0

        # 近期涨幅修正（涨太多估值压力大）
        if p20 > 0.15:
            valuation_bias -= 1.5
        elif p20 > 0.08:
            valuation_bias -= 0.5
        elif p20 < -0.15:
            valuation_bias += 1.0

        # 映射到概率
        bull_prob = 0.333 + valuation_bias * 0.08
        bull_prob = max(0.10, min(0.80, bull_prob))
        bear_prob = max(0.10, min(0.80, 1.0 - bull_prob - 0.2))
        neutral_prob = max(0.10, 1.0 - bull_prob - bear_prob)

        # 基本面分析置信度适中（慢变量，不确定性高）
        confidence = 0.45 + abs(valuation_bias) * 0.05
        confidence = min(0.75, confidence)

        intensity = min(8.0, abs(valuation_bias) * 1.5 + 2.0)

        direction = (
            "BULLISH" if bull_prob > bear_prob + 0.1
            else "BEARISH" if bear_prob > bull_prob + 0.1
            else "NEUTRAL"
        )

        val_desc = (
            "极度低估区" if valuation_bias >= 2 else
            "偏低估" if valuation_bias > 0 else
            "极度高估区" if valuation_bias <= -2 else
            "偏高估" if valuation_bias < 0 else
            "合理估值"
        )

        return AgentOutput(
            agent_type=self.agent_type,
            direction=direction,
            bullish_prob=bull_prob,
            bearish_prob=bear_prob,
            neutral_prob=neutral_prob,
            confidence=confidence,
            intensity=intensity,
            reasoning=f"{val_desc}，FG={fg:.0f}，20日{p20:+.1%}",
            data_used=self._data_sources(),
        )

    def _data_sources(self):
        return ["M10.sentiment.fear_greed", "M9.price_cache.20d_return", "M10.sentiment.adr"]
