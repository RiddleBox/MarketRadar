"""
m11_agent_sim/agents/policy_agent.py — 政策敏感型 Agent

角色定位：
  A股市场最具特色的参与者之一。对政策信号（降准/降息/财政刺激/产业政策）
  高度敏感，"闻风而动"，在政策信号发出后第一时间形成看多/看空判断。

数据来源：M1/M2 信号库（signal_type=policy_document / official_announcement）
行为特征：
  - 政策利好 + 高强度 → 强烈看多，拉高多方概率
  - 政策收紧（加息/监管）→ 看空
  - 无明确政策信号 → 跟随上游共识，衰减至中性
"""
from __future__ import annotations

from typing import List

from ..base_agent import BaseMarketAgent
from ..schemas import AgentConfig, AgentOutput, MarketInput


class PolicySensitiveAgent(BaseMarketAgent):
    """政策敏感型 Agent — A股特有"""

    agent_type = "policy"
    default_weight = 0.20

    def _build_system_prompt(self) -> str:
        return (
            "你是一个专注于中国宏观政策的市场分析师，擅长解读央行/财政部/证监会政策信号对A股的影响。"
            "你的判断优先基于政策信号，弱化技术面和情绪面。"
            "判断原则：明确政策利好(降准/降息/刺激)→BULLISH；明确政策收紧→BEARISH；无明确信号→NEUTRAL。"
            "只输出 JSON，格式：\n"
            '{"direction": "BULLISH|BEARISH|NEUTRAL", '
            '"bullish_prob": 0.0~1.0, "bearish_prob": 0.0~1.0, "neutral_prob": 0.0~1.0, '
            '"confidence": 0.0~1.0, "intensity": 0.0~10.0, "reasoning": "简要推理（50字内）"}'
        )

    def _build_prompt(self, market_input: MarketInput, upstream_context) -> str:
        sig = market_input.signals
        lines = [
            f"市场：{market_input.market}  日期：{market_input.timestamp.strftime('%Y-%m-%d')}",
            f"事件：{market_input.event_description or '无特定事件'}",
            "",
            "【政策/官方信号统计】",
            f"  看多信号：{sig.bullish_count}条  看空：{sig.bearish_count}条  中性：{sig.neutral_count}条",
            f"  平均强度：{sig.avg_intensity:.1f}/10  平均置信：{sig.avg_confidence:.1f}/10",
            f"  主导信号类型：{sig.dominant_signal_type or '未知'}",
        ]
        if sig.recent_signals:
            lines.append("  近期信号摘要：")
            for s in sig.recent_signals[:3]:
                lines.append(
                    f"    [{s.get('signal_type','')}] {s.get('description','')[:40]} "
                    f"强度{s.get('intensity_score',0)}"
                )
        if upstream_context:
            lines += ["", "【其他分析师判断（供参考，你的判断独立）】"]
            for uc in upstream_context:
                lines.append(f"  {uc.agent_name}: {uc.direction} 置信{uc.confidence:.0%}")
        lines.append("\n请从政策面角度给出你的判断：")
        return "\n".join(lines)

    def _analyze_rule_based(
        self, market_input: MarketInput, upstream_context: List[AgentOutput]
    ) -> AgentOutput:
        """规则分析：基于信号统计直接推断"""
        sig = market_input.signals
        total = sig.bullish_count + sig.bearish_count + sig.neutral_count or 1

        bull_ratio = sig.bullish_count / total
        bear_ratio = sig.bearish_count / total
        intensity_norm = min(sig.avg_intensity / 10.0, 1.0)

        # 政策信号有强度时放大
        if sig.avg_intensity >= 7:
            bull_prob = 0.3 + bull_ratio * 0.5
            bear_prob = 0.1 + bear_ratio * 0.5
        elif sig.avg_intensity >= 4:
            bull_prob = 0.33 + (bull_ratio - bear_ratio) * 0.3
            bear_prob = 0.33 - (bull_ratio - bear_ratio) * 0.3
        else:
            # 无明确政策信号，向中性收缩
            bull_prob = 0.333
            bear_prob = 0.333

        bull_prob = max(0.05, min(0.9, bull_prob))
        bear_prob = max(0.05, min(0.9, bear_prob))
        neutral_prob = max(0.05, 1.0 - bull_prob - bear_prob)

        direction = (
            "BULLISH" if bull_prob > bear_prob + 0.1
            else "BEARISH" if bear_prob > bull_prob + 0.1
            else "NEUTRAL"
        )
        confidence = min(0.9, intensity_norm * 0.8 + (abs(bull_ratio - bear_ratio)) * 0.4)

        return AgentOutput(
            agent_type=self.agent_type,
            direction=direction,
            bullish_prob=bull_prob,
            bearish_prob=bear_prob,
            neutral_prob=neutral_prob,
            confidence=confidence,
            intensity=sig.avg_intensity,
            reasoning=f"政策信号: 多{sig.bullish_count}/空{sig.bearish_count}，强度{sig.avg_intensity:.1f}",
            data_used=self._data_sources(),
        )

    def _data_sources(self):
        return ["M2.signals.policy", "M2.signals.official_announcement"]
