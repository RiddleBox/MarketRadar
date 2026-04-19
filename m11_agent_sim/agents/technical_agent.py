"""
m11_agent_sim/agents/technical_agent.py — 技术面型 Agent

角色定位：
  纯技术分析师，看均线/量比/趋势，不关心政策和情绪新闻。
  在A股中占比约20%，游资和部分散户的主要决策依据。

数据来源：M9 价格缓存（均线、量比）
行为特征：
  - 价格站上 MA5 且 MA5 > MA20（多头排列）→ 看多
  - 价格跌破 MA5 且量比放大 → 确认下跌，看空
  - 量比 > 2 + 价格涨 → 放量突破，强烈看多
  - 量比 < 0.5 → 缩量，方向信号弱，倾向中性
"""
from __future__ import annotations

from typing import List

from ..base_agent import BaseMarketAgent
from ..schemas import AgentOutput, MarketInput


class TechnicalAgent(BaseMarketAgent):
    """技术面型 Agent"""

    agent_type = "technical"
    default_weight = 0.15

    def _build_system_prompt(self) -> str:
        return (
            "你是一个纯技术分析师，只看K线、均线、量比等技术指标，不看新闻和政策。"
            "判断原则：均线多头排列+量比放大+持续上涨→BULLISH；均线空头排列+量比放大+持续下跌→BEARISH；信号混合或较弱→NEUTRAL。"
            "不要过度预测反转，趋势持续的概率高于反转。"
            "只输出 JSON，格式：\n"
            '{"direction": "BULLISH|BEARISH|NEUTRAL", '
            '"bullish_prob": 0.0~1.0, "bearish_prob": 0.0~1.0, "neutral_prob": 0.0~1.0, '
            '"confidence": 0.0~1.0, "intensity": 0.0~10.0, "reasoning": "简要推理（50字内）"}'
        )

    def _build_prompt(self, market_input: MarketInput, upstream_context) -> str:
        p = market_input.price
        consensus = self.upstream_consensus(upstream_context)
        lines = [
            f"市场：{market_input.market}  日期：{market_input.timestamp.strftime('%Y-%m-%d')}",
            "",
            "【技术面数据】",
            f"  当前价：{p.current_price:.3f}",
            f"  5日涨跌：{p.price_5d_chg_pct:+.2%}  20日涨跌：{p.price_20d_chg_pct:+.2%}",
            f"  MA5：{p.ma5:.3f}  MA20：{p.ma20:.3f}",
            f"  站上MA5：{'是' if p.above_ma5 else '否'}  站上MA20：{'是' if p.above_ma20 else '否'}",
            f"  量比：{p.volume_ratio:.2f}",
        ]
        if market_input.recent_extreme_move != 0.0:
            lines.append(f"  近期极端行情：{market_input.recent_extreme_move:+.1%}（距今{market_input.days_since_extreme}天）")
            if abs(market_input.recent_extreme_move) > 0.05:
                lines.append("  提示：近期有大波动，注意观察是延续还是反转，需结合量比和均线判断。")
        lines += [
            "",
            f"【上游情绪参考（可不采用）】",
            f"  共识：{consensus['direction']} 置信{consensus['avg_confidence']:.0%}",
            "\n请从纯技术面角度给出判断：",
        ]
        return "\n".join(lines)

    def _analyze_rule_based(
        self, market_input: MarketInput, upstream_context: List[AgentOutput]
    ) -> AgentOutput:
        p = market_input.price
        score = 0.0   # 技术得分，正为多，负为空

        # 均线排列
        if p.above_ma5 and p.above_ma20:
            if p.ma5 > p.ma20:
                score += 2.0   # 多头排列
            else:
                score += 0.5
        elif not p.above_ma5 and not p.above_ma20:
            if p.ma5 < p.ma20:
                score -= 2.0   # 空头排列
            else:
                score -= 0.5
        elif p.above_ma5 and not p.above_ma20:
            score += 0.5       # 短线好转

        # 近期涨跌
        score += p.price_5d_chg_pct * 5     # 5日+1% → +0.05
        score += p.price_20d_chg_pct * 2    # 20日+1% → +0.02

        # 量比
        if p.volume_ratio > 2.0:
            score = score * 1.3   # 放量放大趋势
        elif p.volume_ratio < 0.5:
            score = score * 0.5   # 缩量减弱信号

        # 止盈/均值回归元规则
        if p.price_5d_chg_pct > 0.08:
            score -= 3.0   # 5日涨超8%，强获利了结压力
        elif p.price_5d_chg_pct > 0.05:
            score -= 1.5   # 5日涨超5%，适度回调压力
        elif p.price_5d_chg_pct < -0.08:
            score += 2.0   # 5日跌超8%，技术反弹可能
        elif p.price_5d_chg_pct < -0.05:
            score += 1.0   # 5日跌超5%，适度反弹可能

        # 近期大涨后转跌 → 趋势反转信号（最强信号）
        if p.price_20d_chg_pct > 0.10 and p.price_5d_chg_pct < -0.02:
            score -= 4.0   # 20日大涨但5日转跌，获利了结反转
        elif p.price_20d_chg_pct > 0.05 and p.price_5d_chg_pct < -0.03:
            score -= 2.5

        # 连续下跌趋势确认
        if p.price_5d_chg_pct < -0.03 and p.price_20d_chg_pct < -0.05:
            score -= 1.5

        # 极端反转：大涨后立即大跌（5日跌超5%且20日涨超10%）
        if p.price_5d_chg_pct < -0.05 and p.price_20d_chg_pct > 0.08:
            score -= 5.0

        # recent_extreme_move 补充
        if market_input.recent_extreme_move > 0.06 and market_input.days_since_extreme <= 3:
            score -= 1.5
        elif market_input.recent_extreme_move < -0.06 and market_input.days_since_extreme <= 3:
            score += 1.0

        # 20日超买超卖
        if p.price_20d_chg_pct > 0.15:
            score -= 1.5
        elif p.price_20d_chg_pct < -0.15:
            score += 1.0

        # score 映射到概率（sigmoid-like）
        import math
        bull_prob = 1 / (1 + math.exp(-score * 0.8))
        bear_prob = 1 / (1 + math.exp(score * 0.8))
        # 保留一定中性概率
        bull_prob = bull_prob * 0.8 + 0.1
        bear_prob = bear_prob * 0.8 + 0.1
        neutral_prob = max(0.05, 1.0 - bull_prob - bear_prob)

        confidence = min(0.85, 0.3 + abs(score) * 0.1 + (p.volume_ratio - 1) * 0.05)
        confidence = max(0.1, confidence)
        intensity = min(10.0, abs(score) * 1.5 + 1.0)

        direction = (
            "BULLISH" if bull_prob > bear_prob + 0.1
            else "BEARISH" if bear_prob > bull_prob + 0.1
            else "NEUTRAL"
        )

        ma_desc = "多头排列" if (p.above_ma5 and p.above_ma20 and p.ma5 > p.ma20) else (
            "空头排列" if (not p.above_ma5 and not p.above_ma20 and p.ma5 < p.ma20) else "均线纠缠"
        )

        return AgentOutput(
            agent_type=self.agent_type,
            direction=direction,
            bullish_prob=bull_prob,
            bearish_prob=bear_prob,
            neutral_prob=neutral_prob,
            confidence=confidence,
            intensity=intensity,
            reasoning=f"{ma_desc}，量比{p.volume_ratio:.1f}，5日{p.price_5d_chg_pct:+.1%}",
            data_used=self._data_sources(),
        )

    def _data_sources(self):
        return ["M9.price_cache.ma5", "M9.price_cache.ma20", "M9.price_cache.volume_ratio"]
