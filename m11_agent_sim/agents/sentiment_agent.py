"""
m11_agent_sim/agents/sentiment_agent.py — 情绪型散户 Agent

角色定位：
  跟随市场情绪的散户群体，是市场中情绪传染的主要承载者。
  容易被恐惧和贪婪驱动，在情绪极值时行为最为非理性。

数据来源：M10 FearGreed 指数、微博情绪、百度热搜热度
行为特征：
  - FG > 70（贪婪）→ 追涨，看多（但置信度随 FG 升高而降低，极度贪婪时是反向信号）
  - FG < 30（恐惧）→ 恐慌性卖出，看空（但极度恐惧 FG<20 是历史买点）
  - 热点板块集中 → 跟风追板
  - 上游机构/游资已形成共识 → 情绪型散户跟随，形成羊群效应
"""
from __future__ import annotations

from typing import List

from ..base_agent import BaseMarketAgent
from ..schemas import AgentOutput, MarketInput


class SentimentRetailAgent(BaseMarketAgent):
    """情绪型散户 Agent"""

    agent_type = "sentiment_retail"
    default_weight = 0.20

    def _build_system_prompt(self) -> str:
        return (
            "你代表A股市场中受情绪驱动的散户群体。"
            "你的判断主要来自市场氛围、热点讨论和跟风行为，而非理性分析。"
            "注意：极度贪婪（FG>80）时你会追高，但这往往是危险信号；"
            "极度恐惧（FG<20）时你会割肉，但这往往是买点。"
            "判断原则：FG>60且涨跌比>0.6→BULLISH；FG<40且涨跌比<0.4→BEARISH；其余→NEUTRAL。"
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
            "",
            "【情绪数据】",
            f"  恐贪指数：{sent.fear_greed_index:.1f} ({sent.sentiment_label})",
            f"  微博情绪均值：{sent.weibo_sentiment:+.2f}（-1极度悲观~+1极度乐观）",
            f"  涨跌比：{sent.advance_decline_ratio:.1%}",
            f"  热点板块：{', '.join(sent.hot_sectors[:5]) or '无'}",
            "",
            "【其他分析师已形成的共识（你可能会跟风）】",
            f"  {consensus['direction']} (多{consensus['bullish_prob']:.0%}/空{consensus['bearish_prob']:.0%}) "
            f"置信{consensus['avg_confidence']:.0%}",
        ]
        if upstream_context:
            for uc in upstream_context:
                lines.append(f"  {uc.agent_name}: {uc.direction} — {uc.reasoning[:30]}")
        lines.append("\n请从情绪驱动的散户视角给出判断（注意极值时的反向效应）：")
        return "\n".join(lines)

    def _analyze_rule_based(
        self, market_input: MarketInput, upstream_context: List[AgentOutput]
    ) -> AgentOutput:
        fg = market_input.sentiment.fear_greed_index
        weibo = market_input.sentiment.weibo_sentiment
        adr = market_input.sentiment.advance_decline_ratio
        consensus = self.upstream_consensus(upstream_context)

        # 情绪直接映射（散户跟着情绪走）
        # FG → 多方概率（注意极值时的非线性）
        if fg >= 80:
            raw_bull = 0.75
            intensity = 9.0
            conf = 0.20   # 极低置信（极度贪婪=反转信号，散户判断不可靠）
        elif fg >= 60:
            raw_bull = 0.60
            intensity = 7.0
            conf = 0.45
        elif fg >= 40:
            raw_bull = 0.45
            intensity = 4.0
            conf = 0.40
        elif fg >= 20:
            raw_bull = 0.30
            intensity = 7.0
            conf = 0.45
        else:
            raw_bull = 0.20
            intensity = 9.0
            conf = 0.20   # 极低置信（极度恐惧=反转信号）

        # 微博情绪修正
        raw_bull += weibo * 0.10

        # 涨跌比修正
        raw_bull += (adr - 0.5) * 0.15

        # 羊群效应：上游已形成共识时，散户跟随
        if consensus["avg_confidence"] > 0.6:
            follow_strength = 0.3
            raw_bull = raw_bull * (1 - follow_strength) + consensus["bullish_prob"] * follow_strength

        bull_prob = max(0.05, min(0.92, raw_bull))
        bear_prob = max(0.05, min(0.92, 1.0 - bull_prob - 0.15))
        neutral_prob = max(0.03, 1.0 - bull_prob - bear_prob)

        direction = (
            "BULLISH" if bull_prob > bear_prob + 0.1
            else "BEARISH" if bear_prob > bull_prob + 0.1
            else "NEUTRAL"
        )

        fg_desc = (
            "极度贪婪追高" if fg >= 80 else
            "情绪偏热" if fg >= 60 else
            "情绪中性" if fg >= 40 else
            "情绪偏冷" if fg >= 20 else
            "极度恐惧割肉"
        )

        return AgentOutput(
            agent_type=self.agent_type,
            direction=direction,
            bullish_prob=bull_prob,
            bearish_prob=bear_prob,
            neutral_prob=neutral_prob,
            confidence=conf,
            intensity=intensity,
            reasoning=f"FG={fg:.0f} {fg_desc}，微博{weibo:+.2f}",
            data_used=self._data_sources(),
        )

    def _data_sources(self):
        return ["M10.sentiment.fear_greed", "M10.sentiment.weibo", "M10.sentiment.adr"]
