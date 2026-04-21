"""
m11_agent_sim/agents/contrarian_agent.py — 反向交易员 Agent

角色定位：
  市场中的"逆向思维者"，专门识别"利好出尽"和"恐慌过度"场景。
  当市场情绪极端时（恐贪指数 > 80 或 < 20），反向判断。

设计原则：
  - 情绪过热（fear_greed_index > 80）+ 政策利好 → 看空（利好出尽）
  - 情绪极度恐惧（fear_greed_index < 20）+ 利空信号 → 看多（超跌反弹）
  - 正常情绪区间（20~80）→ 低权重跟随上游共识

行为特征：
  - 正常情况下权重极低（0.05），避免干扰主流判断
  - 情绪极值时权重提升（0.25），发挥"刹车"作用
  - 推理透明：明确说明反向逻辑（"利好已被市场提前消化"）

校准目标：
  - 提升极值事件（9-30、11-08、12-12）的方向准确率
  - 降低 Brier Score（当前 0.69 → 目标 < 0.30）
  - 提升极值召回率（当前 33.3% → 目标 60%+）
"""
from __future__ import annotations

from typing import List

from ..base_agent import BaseMarketAgent
from ..schemas import AgentConfig, AgentOutput, MarketInput


class ContrarianAgent(BaseMarketAgent):
    """反向交易员 Agent — 识别利好出尽和恐慌过度"""

    agent_type = "contrarian"
    default_weight = 0.10  # 正常情况低权重，极值时动态提升

    def _build_system_prompt(self) -> str:
        return (
            "你是一个反向交易员，专门识别市场情绪极端时的反转机会。"
            "判断原则：\n"
            "1. 情绪过热（恐贪指数>80）+ 政策利好 → BEARISH（利好出尽，追高风险大）\n"
            "2. 情绪极度恐惧（恐贪指数<20）+ 利空信号 → BULLISH（恐慌过度，超跌反弹）\n"
            "3. 正常情绪区间（20~80）→ NEUTRAL（跟随市场共识）\n"
            "只输出 JSON，格式：\n"
            '{"direction": "BULLISH|BEARISH|NEUTRAL", '
            '"bullish_prob": 0.0~1.0, "bearish_prob": 0.0~1.0, "neutral_prob": 0.0~1.0, '
            '"confidence": 0.0~1.0, "intensity": 0.0~10.0, "reasoning": "简要推理（50字内）"}'
        )

    def _build_prompt(self, market_input: MarketInput, upstream_context) -> str:
        sig = market_input.signals
        sent = market_input.sentiment
        lines = [
            f"市场：{market_input.market}  日期：{market_input.timestamp.strftime('%Y-%m-%d')}",
            f"事件：{market_input.event_description or '无特定事件'}",
            "",
            "【情绪数据】",
            f"  恐贪指数：{sent.fear_greed_index:.1f} ({sent.sentiment_label})",
            f"  北向资金：{sent.northbound_flow:+.1f}亿",
            f"  涨跌比：{sent.advance_decline_ratio:.1%}",
            "",
            "【信号统计】",
            f"  看多信号：{sig.bullish_count}条  看空：{sig.bearish_count}条",
            f"  平均强度：{sig.avg_intensity:.1f}/10",
            f"  主导信号类型：{sig.dominant_signal_type or '未知'}",
        ]
        if upstream_context:
            lines += ["", "【其他分析师判断（供参考）】"]
            for uc in upstream_context:
                lines.append(f"  {uc.agent_name}: {uc.direction} 置信{uc.confidence:.0%}")
        lines.append("\n请从反向交易视角给出你的判断：")
        return "\n".join(lines)

    def _analyze_rule_based(
        self, market_input: MarketInput, upstream_context: List[AgentOutput]
    ) -> AgentOutput:
        """规则分析：基于情绪极值 + 信号类型反向判断"""
        sig = market_input.signals
        sent = market_input.sentiment
        fg_index = sent.fear_greed_index

        # 计算上游共识（正常情况跟随）
        consensus = self.upstream_consensus(upstream_context)

        # 情绪过热场景（利好出尽）- 不再依赖信号方向
        if fg_index > 70:
            direction = "BEARISH"
            bull_prob = 0.10
            bear_prob = 0.80
            neutral_prob = 0.10
            confidence = min(0.95, (fg_index - 70) / 30 * 0.6 + 0.60)
            intensity = min(10.0, sig.avg_intensity * 1.2)
            reasoning = (
                f"情绪过热({fg_index:.0f})，无论信号方向，"
                "市场已提前消化，追高风险大 → 看空"
            )

        # 情绪极度恐惧场景（超跌反弹）- 不再依赖信号方向
        elif fg_index < 30:
            direction = "BULLISH"
            bull_prob = 0.70
            bear_prob = 0.15
            neutral_prob = 0.15
            confidence = min(0.85, (30 - fg_index) / 30 * 0.5 + 0.35)
            intensity = min(10.0, sig.avg_intensity * 1.2)
            reasoning = (
                f"情绪极度恐惧({fg_index:.0f})，无论信号方向，"
                "恐慌过度，超跌反弹概率高 → 看多"
            )

        # 正常情绪区间（跟随上游共识，低置信）
        else:
            direction = consensus["direction"]
            bull_prob = consensus["bullish_prob"]
            bear_prob = consensus["bearish_prob"]
            neutral_prob = max(0.05, 1.0 - bull_prob - bear_prob)
            confidence = 0.15  # 低置信，避免干扰主流判断
            intensity = 3.0
            reasoning = f"情绪正常({fg_index:.0f})，无反向信号 → 跟随共识（阈值70/30）"

        return AgentOutput(
            agent_type=self.agent_type,
            direction=direction,
            bullish_prob=bull_prob,
            bearish_prob=bear_prob,
            neutral_prob=neutral_prob,
            confidence=confidence,
            intensity=intensity,
            reasoning=reasoning,
            data_used=self._data_sources(),
        )

    def _data_sources(self):
        return ["M10.sentiment.fear_greed_index", "M2.signals.policy", "M2.signals.official_announcement"]

    @staticmethod
    def should_boost_weight(market_input: MarketInput) -> bool:
        """
        判断是否应提升 ContrarianAgent 权重。

        返回 True 时，AgentNetwork 应将权重从 0.05 提升至 0.25。
        阈值：fear_greed_index > 70 或 < 30
        """
        fg_index = market_input.sentiment.fear_greed_index
        return fg_index > 70 or fg_index < 30
