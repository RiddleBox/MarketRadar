"""
m11_agent_sim/base_agent.py — BaseMarketAgent 抽象基类

设计原则（D-05）：
  序列传导模式下，每个 Agent 接收：
    1. market_input      : 当前市场快照（所有 Agent 共享同一份）
    2. upstream_context  : 上游 Agent 的输出列表（序列传导的核心）

  Agent 分析后输出 AgentOutput，包含方向/概率/置信度/推理。

  graph 模式（Phase 2）预留：
    upstream_context 会包含所有邻居节点的输出，
    Agent 可根据邻居权重决定受影响程度。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from .schemas import AgentConfig, AgentOutput, Direction, MarketInput

logger = logging.getLogger(__name__)


class BaseMarketAgent(ABC):
    """
    市场 Agent 抽象基类

    子类需实现：
      _analyze_with_llm(market_input, upstream_context) → AgentOutput
      或
      _analyze_rule_based(market_input, upstream_context) → AgentOutput

    默认使用 LLM 分析，子类可 override _build_prompt() 定制 prompt。
    如果 LLM 不可用或 use_llm=False，退化为规则分析。
    """

    agent_type: str = "base"
    default_weight: float = 0.2

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm_client=None,
        use_llm: bool = True,
    ):
        self.config = config or AgentConfig(
            agent_type=self.agent_type,
            name=self.__class__.__name__,
            weight=self.default_weight,
        )
        self.llm_client = llm_client
        self.use_llm = use_llm and (llm_client is not None)

    # ── 公开接口 ─────────────────────────────────────────────

    def analyze(
        self,
        market_input: MarketInput,
        upstream_context: Optional[List[AgentOutput]] = None,
    ) -> AgentOutput:
        """
        分析市场输入，返回 AgentOutput。

        upstream_context: 上游 Agent 的输出列表（序列传导时由 AgentNetwork 注入）
        """
        upstream_context = upstream_context or []
        try:
            if self.use_llm:
                output = self._analyze_with_llm(market_input, upstream_context)
            else:
                output = self._analyze_rule_based(market_input, upstream_context)
            output.agent_type = self.agent_type
            output.agent_name = self.config.name or self.__class__.__name__
            return output.normalize_probs()
        except Exception as e:
            logger.warning(f"[{self.__class__.__name__}] 分析失败，使用中性默认值: {e}")
            return self._neutral_output(reason=str(e))

    # ── 子类实现 ─────────────────────────────────────────────

    def _analyze_with_llm(
        self,
        market_input: MarketInput,
        upstream_context: List[AgentOutput],
    ) -> AgentOutput:
        """LLM 分析（默认实现，子类可 override _build_prompt 定制）"""
        prompt = self._build_prompt(market_input, upstream_context)
        system = self._build_system_prompt()

        # 构造 messages 格式
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]

        response = self.llm_client.chat_completion(messages=messages, module_name="m11_agent_sim")
        return self._parse_llm_response(response, market_input)

    @abstractmethod
    def _analyze_rule_based(
        self,
        market_input: MarketInput,
        upstream_context: List[AgentOutput],
    ) -> AgentOutput:
        """
        规则分析（必须实现）：
        - LLM 不可用时的降级方案
        - 也可作为单元测试的 mock 替代
        """

    def _build_system_prompt(self) -> str:
        """构建 system prompt，子类可 override"""
        return (
            f"你是一个{self.config.name or self.agent_type}市场分析师。"
            "根据市场数据，判断市场短期（1~5个交易日）的方向。"
            "判断原则：信号明确时输出BULLISH或BEARISH，信号混合或较弱时输出NEUTRAL。"
            "只输出 JSON，格式：\n"
            '{"direction": "BULLISH|BEARISH|NEUTRAL", '
            '"bullish_prob": 0.0~1.0, '
            '"bearish_prob": 0.0~1.0, '
            '"neutral_prob": 0.0~1.0, '
            '"confidence": 0.0~1.0, '
            '"intensity": 0.0~10.0, '
            '"reasoning": "简要推理（50字内）"}'
        )

    def _build_prompt(
        self,
        market_input: MarketInput,
        upstream_context: List[AgentOutput],
    ) -> str:
        """构建用户 prompt，子类可 override 添加特定数据"""
        lines = [
            f"市场：{market_input.market}",
            f"时间：{market_input.timestamp.strftime('%Y-%m-%d')}",
            f"事件：{market_input.event_description or '（无特定事件）'}",
            "",
            "【情绪数据】",
            f"  恐贪指数：{market_input.sentiment.fear_greed_index:.1f} ({market_input.sentiment.sentiment_label})",
            f"  北向资金：{market_input.sentiment.northbound_flow:+.1f}亿",
            f"  涨跌比：{market_input.sentiment.advance_decline_ratio:.1%}",
            "",
            "【信号数据】",
            f"  看多信号：{market_input.signals.bullish_count}条",
            f"  看空信号：{market_input.signals.bearish_count}条",
            f"  平均强度：{market_input.signals.avg_intensity:.1f}",
        ]

        if upstream_context:
            lines += ["", "【上游分析师判断】"]
            for uc in upstream_context:
                lines.append(
                    f"  {uc.agent_name}: {uc.direction} "
                    f"(多{uc.bullish_prob:.0%}/空{uc.bearish_prob:.0%}) "
                    f"置信{uc.confidence:.0%} — {uc.reasoning[:40]}"
                )

        lines += ["", "请基于以上信息，从你的角色视角给出判断："]
        return "\n".join(lines)

    # ── 解析与工具 ────────────────────────────────────────────

    def _parse_llm_response(
        self, response: str, market_input: MarketInput
    ) -> AgentOutput:
        """解析 LLM JSON 响应，失败时退化为规则分析"""
        import json, re
        try:
            # 提取 JSON 块
            match = re.search(r'\{[^{}]+\}', response, re.DOTALL)
            if not match:
                raise ValueError("未找到 JSON")
            data = json.loads(match.group())
            return AgentOutput(
                agent_type=self.agent_type,
                direction=data.get("direction", "NEUTRAL"),
                bullish_prob=float(data.get("bullish_prob", 0.333)),
                bearish_prob=float(data.get("bearish_prob", 0.333)),
                neutral_prob=float(data.get("neutral_prob", 0.334)),
                confidence=float(data.get("confidence", 0.5)),
                intensity=float(data.get("intensity", 5.0)),
                reasoning=data.get("reasoning", ""),
                data_used=self._data_sources(),
            )
        except Exception as e:
            logger.warning(f"[{self.__class__.__name__}] LLM 响应解析失败: {e}，退化为规则分析")
            return self._analyze_rule_based(market_input, [])

    def _neutral_output(self, reason: str = "") -> AgentOutput:
        """返回中性默认输出"""
        return AgentOutput(
            agent_type=self.agent_type,
            agent_name=self.config.name or self.__class__.__name__,
            direction="NEUTRAL",
            bullish_prob=0.333,
            bearish_prob=0.333,
            neutral_prob=0.334,
            confidence=0.1,
            intensity=1.0,
            reasoning=f"数据不足或分析失败: {reason}",
        )

    def _data_sources(self) -> list[str]:
        """子类声明自己使用的数据维度，用于 AgentOutput.data_used"""
        return []

    # ── 上游情绪汇总工具（供子类使用）────────────────────────

    @staticmethod
    def upstream_consensus(upstream: List[AgentOutput]) -> dict:
        """
        计算上游 Agent 的加权共识。

        返回：
          direction    : 上游加权方向
          bullish_prob : 上游加权多方概率
          bearish_prob : 上游加权空方概率
          avg_confidence : 上游平均置信度
        """
        if not upstream:
            return {
                "direction": "NEUTRAL",
                "bullish_prob": 0.333,
                "bearish_prob": 0.333,
                "avg_confidence": 0.5,
            }
        total_conf = sum(u.confidence for u in upstream) or 1.0
        w_bull = sum(u.bullish_prob * u.confidence for u in upstream) / total_conf
        w_bear = sum(u.bearish_prob * u.confidence for u in upstream) / total_conf
        direction: Direction = (
            "BULLISH" if w_bull > w_bear and w_bull > 0.4
            else "BEARISH" if w_bear > w_bull and w_bear > 0.4
            else "NEUTRAL"
        )
        return {
            "direction": direction,
            "bullish_prob": w_bull,
            "bearish_prob": w_bear,
            "avg_confidence": total_conf / len(upstream),
        }
