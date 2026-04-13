"""
m11_agent_sim/agents/northbound_agent.py — 北向跟随型 Agent

角色定位：
  跟随外资（沪深港通北向资金）方向操作的机构/大户。
  逻辑：外资信息优势和风险定价能力强，其方向有领先性。

数据来源：M10 SentimentContext.northbound_flow
行为特征：
  - 北向大幅净流入（>100亿）→ 强烈看多
  - 北向持续净流出（<-50亿）→ 看空
  - 北向接近0 → 中性，参考上游共识
  - 上游（政策Agent）看多 + 北向也流入 → 共振放大置信度
"""
from __future__ import annotations

from typing import List

from ..base_agent import BaseMarketAgent
from ..schemas import AgentConfig, AgentOutput, MarketInput


class NorthboundFollowerAgent(BaseMarketAgent):
    """北向跟随型 Agent"""

    agent_type = "northbound"
    default_weight = 0.25   # 外资信号权重高

    # 北向资金判断阈值（亿元）
    STRONG_INFLOW = 80.0
    MILD_INFLOW = 20.0
    MILD_OUTFLOW = -20.0
    STRONG_OUTFLOW = -80.0

    def _build_system_prompt(self) -> str:
        return (
            "你是一个专注于北向资金（沪深港通）动向的机构量化分析师。"
            "你高度重视外资流向作为先行指标，同时结合上游分析师的判断。"
            "只输出 JSON，格式：\n"
            '{"direction": "BULLISH|BEARISH|NEUTRAL", '
            '"bullish_prob": 0.0~1.0, "bearish_prob": 0.0~1.0, "neutral_prob": 0.0~1.0, '
            '"confidence": 0.0~1.0, "intensity": 0.0~10.0, "reasoning": "简要推理（50字内）"}'
        )

    def _build_prompt(self, market_input: MarketInput, upstream_context) -> str:
        sent = market_input.sentiment
        consensus = self.upstream_consensus(upstream_context)
        lines = [
            f"市场：{market_input.market}  日期：{market_input.timestamp.strftime('%Y-%m-%d')}",
            f"事件：{market_input.event_description or '无特定事件'}",
            "",
            "【北向资金数据】",
            f"  今日净流入：{sent.northbound_flow:+.1f}亿元",
            f"  涨跌家数比：{sent.advance_decline_ratio:.1%}",
            "",
            "【上游政策分析师判断】",
            f"  共识方向：{consensus['direction']} "
            f"(多{consensus['bullish_prob']:.0%}/空{consensus['bearish_prob']:.0%}) "
            f"置信{consensus['avg_confidence']:.0%}",
        ]
        if upstream_context:
            for uc in upstream_context:
                lines.append(f"  {uc.agent_name}: {uc.direction} — {uc.reasoning[:40]}")
        lines.append("\n请结合北向资金和上游判断，给出你的分析：")
        return "\n".join(lines)

    def _analyze_rule_based(
        self, market_input: MarketInput, upstream_context: List[AgentOutput]
    ) -> AgentOutput:
        flow = market_input.sentiment.northbound_flow
        consensus = self.upstream_consensus(upstream_context)

        # 北向资金信号
        if flow >= self.STRONG_INFLOW:
            nb_bull, nb_bear = 0.70, 0.10
            nb_intensity, nb_conf = 8.0, 0.85
        elif flow >= self.MILD_INFLOW:
            nb_bull, nb_bear = 0.55, 0.20
            nb_intensity, nb_conf = 6.0, 0.65
        elif flow <= self.STRONG_OUTFLOW:
            nb_bull, nb_bear = 0.10, 0.70
            nb_intensity, nb_conf = 8.0, 0.85
        elif flow <= self.MILD_OUTFLOW:
            nb_bull, nb_bear = 0.20, 0.55
            nb_intensity, nb_conf = 6.0, 0.65
        else:
            # 接近0，向上游共识靠拢
            nb_bull = consensus["bullish_prob"]
            nb_bear = consensus["bearish_prob"]
            nb_intensity, nb_conf = 3.0, 0.35

        # 上游共振加成
        if consensus["direction"] == "BULLISH" and nb_bull > 0.5:
            nb_conf = min(0.95, nb_conf + 0.10)
        elif consensus["direction"] == "BEARISH" and nb_bear > 0.5:
            nb_conf = min(0.95, nb_conf + 0.10)
        elif consensus["direction"] != "NEUTRAL" and (
            (consensus["direction"] == "BULLISH") != (nb_bull > nb_bear)
        ):
            # 上游与北向背离，降低置信度
            nb_conf = max(0.1, nb_conf - 0.20)

        nb_neutral = max(0.05, 1.0 - nb_bull - nb_bear)
        direction = (
            "BULLISH" if nb_bull > nb_bear + 0.1
            else "BEARISH" if nb_bear > nb_bull + 0.1
            else "NEUTRAL"
        )

        return AgentOutput(
            agent_type=self.agent_type,
            direction=direction,
            bullish_prob=nb_bull,
            bearish_prob=nb_bear,
            neutral_prob=nb_neutral,
            confidence=nb_conf,
            intensity=nb_intensity,
            reasoning=f"北向{flow:+.0f}亿，上游{consensus['direction']}",
            data_used=self._data_sources(),
        )

    def _data_sources(self):
        return ["M10.sentiment.northbound_flow"]
