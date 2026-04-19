"""
m11_agent_sim/agent_network.py — AgentNetwork 编排器

设计原则（D-05 / D-06）：
  Phase 1: topology="sequential" — 序列传导
    信息流：PolicySensitiveAgent → NorthboundFollowerAgent
                                 → TechnicalAgent
                                 → SentimentRetailAgent
                                 → FundamentalAgent
    每个 Agent 的 upstream_context 包含所有已执行的上游 Agent 输出。

  Phase 2: topology="graph" — 图结构互动（骨架预留）
    Agent 间加权连接，情绪在图上扩散，迭代至收敛。
    weight_matrix 可外部注入，或从历史数据学习。

输出：SentimentDistribution（方向+概率分布+置信区间）
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Type

import numpy as np

from .base_agent import BaseMarketAgent
from .schemas import (
    AgentConfig,
    AgentOutput,
    MarketInput,
    NetworkConfig,
    SentimentDistribution,
)

logger = logging.getLogger(__name__)

# ── 默认 Agent 类型注册表 ─────────────────────────────────────
def _default_registry() -> Dict[str, Type[BaseMarketAgent]]:
    from .agents import (
        FundamentalAgent,
        NorthboundFollowerAgent,
        PolicySensitiveAgent,
        SentimentRetailAgent,
        TechnicalAgent,
    )
    return {
        "policy":           PolicySensitiveAgent,
        "northbound":       NorthboundFollowerAgent,
        "technical":        TechnicalAgent,
        "sentiment_retail": SentimentRetailAgent,
        "fundamental":      FundamentalAgent,
    }


class AgentNetwork:
    """
    多 Agent 情绪模拟编排器

    用法：
        net = AgentNetwork.from_config_file("a_share")
        result = net.run(market_input)
        print(result.summary())

    或直接传入 NetworkConfig：
        net = AgentNetwork(config=my_config)
    """

    def __init__(
        self,
        config: Optional[NetworkConfig] = None,
        llm_client=None,
        use_llm: bool = False,   # 默认规则模式（离线可用，测试方便）
        agent_registry: Optional[Dict[str, Type[BaseMarketAgent]]] = None,
        min_confidence: float = 0.0,   # 置信度门控阈值（低于此值强制NEUTRAL+no_trade）
    ):
        self.config = config or NetworkConfig()
        self.llm_client = llm_client
        self.use_llm = use_llm
        self.min_confidence = min_confidence
        self.registry = agent_registry or _default_registry()
        self._agents: List[BaseMarketAgent] = self._build_agents()

    # ── 工厂方法 ─────────────────────────────────────────────

    @classmethod
    def from_config_file(
        cls,
        market: str = "a_share",
        topology: str = "sequential",
        llm_client=None,
        use_llm: bool = False,
    ) -> "AgentNetwork":
        """从内置配置文件加载（a_share / hk）"""
        import yaml
        from pathlib import Path
        config_path = Path(__file__).parent / "configs" / f"{market}.yaml"
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}，使用默认 A 股配置")
            return cls._default_a_share(topology, llm_client, use_llm)
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        agents = [AgentConfig(**a) for a in raw.get("agents", [])]
        weight_matrix = raw.get("weight_matrix", {})
        config = NetworkConfig(
            market=raw.get("market", "A_SHARE"),
            topology=topology,
            agents=agents,
            weight_matrix=weight_matrix,
        )
        return cls(config=config, llm_client=llm_client, use_llm=use_llm)

    @classmethod
    def _default_a_share(
        cls, topology: str = "sequential", llm_client=None, use_llm: bool = False,
        min_confidence: float = 0.0,
    ) -> "AgentNetwork":
        """默认 A 股配置（不依赖文件）"""
        config = NetworkConfig(
            market="A_SHARE",
            topology=topology,
            agents=[
                AgentConfig(agent_type="policy",           name="政策分析师", weight=0.20, sequence_pos=0),
                AgentConfig(agent_type="northbound",       name="北向跟随者", weight=0.20, sequence_pos=1),
                AgentConfig(agent_type="technical",        name="技术分析师", weight=0.15, sequence_pos=2),
                AgentConfig(agent_type="sentiment_retail", name="情绪散户",   weight=0.20, sequence_pos=3),
                AgentConfig(agent_type="fundamental",      name="基本面分析师", weight=0.25, sequence_pos=4),
            ],
        )
        return cls(config=config, llm_client=llm_client, use_llm=use_llm, min_confidence=min_confidence)

    # ── 主入口 ────────────────────────────────────────────────

    def run(self, market_input: MarketInput) -> SentimentDistribution:
        """
        运行模拟，返回 SentimentDistribution。

        topology="sequential" → 序列传导
        topology="graph"      → 图扩散（Phase 2 骨架）
        """
        t0 = time.time()
        if self.config.topology == "sequential":
            outputs = self._run_sequential(market_input)
        elif self.config.topology == "graph":
            outputs = self._run_graph(market_input)
        else:
            raise ValueError(f"未知 topology: {self.config.topology}")

        dist = self._aggregate(outputs, market_input)
        dist.simulation_ms = int((time.time() - t0) * 1000)
        dist.topology_used = self.config.topology
        dist.agents_count = len(outputs)

        # 置信度门控：低置信时不交易
        if self.min_confidence > 0 and dist.confidence < self.min_confidence:
            dist.no_trade = True
            dist.direction = "NEUTRAL"
            logger.debug(
                f"[AgentNetwork] 置信度门控: {dist.confidence:.2f} < {self.min_confidence:.2f} → NEUTRAL/no_trade"
            )
        return dist

    # ── 序列传导（Phase 1）────────────────────────────────────

    def _run_sequential(self, market_input: MarketInput) -> List[AgentOutput]:
        """
        序列传导：按 sequence_pos 排序，每个 Agent 接收所有已执行的上游输出。

        信息流：
          Agent[0]（政策）: upstream=[]
          Agent[1]（北向）: upstream=[Agent[0].output]
          Agent[2]（技术）: upstream=[Agent[0].output, Agent[1].output]
          ...
        """
        sorted_agents = sorted(
            self._agents,
            key=lambda a: a.config.sequence_pos,
        )
        outputs: List[AgentOutput] = []
        for agent in sorted_agents:
            if not agent.config.enabled:
                continue
            output = agent.analyze(market_input, upstream_context=list(outputs))
            outputs.append(output)
            logger.debug(
                f"[AgentNetwork] {agent.config.name}: "
                f"{output.direction} 多{output.bullish_prob:.0%} "
                f"置信{output.confidence:.0%} — {output.reasoning[:30]}"
            )
        return outputs

    # ── 图结构（Phase 2 骨架）────────────────────────────────

    def _run_graph(
        self,
        market_input: MarketInput,
        max_iterations: int = 10,
        convergence_threshold: float = 0.01,
    ) -> List[AgentOutput]:
        """
        图结构情绪扩散（Phase 2 骨架）。

        算法：
          1. 初始化：每个 Agent 独立分析（无上游）
          2. 迭代：每轮根据 weight_matrix 更新各节点的 bullish_prob
          3. 收敛：各节点概率变化 < convergence_threshold 则停止

        weight_matrix 格式：
          {from_agent_type: {to_agent_type: influence_weight}}
          例：{"policy": {"sentiment_retail": 0.3}} 表示政策信号对散户有 30% 的影响

        ⚠️ Phase 2 TODO：
          - weight_matrix 目前用经验值，待从 M10 历史数据学习
          - 收敛检测用 L1 范数，后续改用 KL 散度（D-06）
        """
        logger.info("[AgentNetwork] 使用图结构模式（Phase 2 骨架）")

        # Step 1: 初始化（无上游）
        agent_map: Dict[str, BaseMarketAgent] = {
            a.agent_type: a for a in self._agents if a.config.enabled
        }
        current_outputs: Dict[str, AgentOutput] = {}
        for atype, agent in agent_map.items():
            current_outputs[atype] = agent.analyze(market_input, upstream_context=[])

        weight_matrix = self.config.weight_matrix
        if not weight_matrix:
            # 默认经验权重（行为金融学文献参考值）
            weight_matrix = {
                "policy":     {"northbound": 0.15, "sentiment_retail": 0.25, "technical": 0.10},
                "northbound": {"technical": 0.20, "sentiment_retail": 0.30, "fundamental": 0.15},
                "technical":  {"sentiment_retail": 0.20},
                "fundamental": {"sentiment_retail": 0.10},
            }

        # Step 2: 迭代扩散
        for iteration in range(max_iterations):
            new_outputs: Dict[str, AgentOutput] = {}
            max_delta = 0.0

            for atype, agent in agent_map.items():
                # 收集影响该节点的上游
                influencers: List[AgentOutput] = []
                for src_type, targets in weight_matrix.items():
                    if atype in targets and src_type in current_outputs:
                        src_out = current_outputs[src_type]
                        # 按权重缩放置信度（权重越高，上游影响越大）
                        influence_weight = targets[atype]
                        scaled = AgentOutput(
                            agent_type=src_out.agent_type,
                            agent_name=src_out.agent_name,
                            direction=src_out.direction,
                            bullish_prob=src_out.bullish_prob,
                            bearish_prob=src_out.bearish_prob,
                            neutral_prob=src_out.neutral_prob,
                            confidence=src_out.confidence * influence_weight,
                            intensity=src_out.intensity,
                            reasoning=src_out.reasoning,
                        )
                        influencers.append(scaled)

                new_out = agent.analyze(market_input, upstream_context=influencers)
                new_outputs[atype] = new_out

                # 计算变化量
                old_out = current_outputs[atype]
                delta = abs(new_out.bullish_prob - old_out.bullish_prob)
                max_delta = max(max_delta, delta)

            current_outputs = new_outputs
            logger.debug(f"[AgentNetwork/graph] 迭代 {iteration+1}，最大变化量 {max_delta:.4f}")

            if max_delta < convergence_threshold:
                logger.info(f"[AgentNetwork/graph] 收敛于第 {iteration+1} 轮")
                break

        return list(current_outputs.values())

    # ── 聚合 ─────────────────────────────────────────────────

    def _aggregate(
        self, outputs: List[AgentOutput], market_input: MarketInput
    ) -> SentimentDistribution:
        """
        将多个 AgentOutput 按权重聚合为 SentimentDistribution。

        权重来自 AgentConfig.weight × AgentOutput.confidence（双重加权）：
          最终权重 = config_weight × confidence（归一化后）
        """
        if not outputs:
            return SentimentDistribution(
                market=market_input.market,
                event_description=market_input.event_description,
                timestamp=market_input.timestamp,
            )

        # 构建权重映射
        weight_map: Dict[str, float] = {
            a.agent_type: a.config.weight for a in self._agents
        }

        total_w = 0.0
        w_bull = 0.0
        w_bear = 0.0
        w_neutral = 0.0
        w_intensity = 0.0
        w_confidence = 0.0
        weighted_bulls: List[float] = []
        weights: List[float] = []

        for out in outputs:
            cfg_w = weight_map.get(out.agent_type, 1.0 / len(outputs))
            effective_w = cfg_w * (0.3 + out.confidence * 0.7)   # 低置信时衰减，不完全忽略
            total_w += effective_w
            w_bull += out.bullish_prob * effective_w
            w_bear += out.bearish_prob * effective_w
            w_neutral += out.neutral_prob * effective_w
            w_intensity += out.intensity * effective_w
            w_confidence += out.confidence * effective_w
            weighted_bulls.append(out.bullish_prob)
            weights.append(effective_w)

        if total_w == 0:
            total_w = 1.0

        bull = w_bull / total_w
        bear = w_bear / total_w
        neutral = w_neutral / total_w
        intensity = w_intensity / total_w
        confidence = w_confidence / total_w

        # 归一化
        total_prob = bull + bear + neutral
        if total_prob > 0:
            bull /= total_prob
            bear /= total_prob
            neutral /= total_prob

        # 综合方向
        direction = (
            "BULLISH" if bull > bear + 0.07
            else "BEARISH" if bear > bull + 0.07
            else "NEUTRAL"
        )

        # 95% 置信区间（Bootstrap 近似）
        w_arr = np.array(weights) / sum(weights)
        bull_arr = np.array(weighted_bulls)
        ci_low = float(np.percentile(bull_arr, 5))
        ci_high = float(np.percentile(bull_arr, 95))

        return SentimentDistribution(
            timestamp=market_input.timestamp,
            market=market_input.market,
            event_description=market_input.event_description,
            bullish_prob=round(bull, 4),
            bearish_prob=round(bear, 4),
            neutral_prob=round(neutral, 4),
            direction=direction,
            intensity=round(intensity, 2),
            confidence=round(confidence, 3),
            bullish_prob_ci_low=round(ci_low, 4),
            bullish_prob_ci_high=round(ci_high, 4),
            agent_outputs=outputs,
        )

    # ── 内部构建 ─────────────────────────────────────────────

    def _build_agents(self) -> List[BaseMarketAgent]:
        agents = []
        for cfg in self.config.agents:
            if not cfg.enabled:
                continue
            agent_cls = self.registry.get(cfg.agent_type)
            if agent_cls is None:
                logger.warning(f"[AgentNetwork] 未知 Agent 类型: {cfg.agent_type}，跳过")
                continue
            agent = agent_cls(
                config=cfg,
                llm_client=self.llm_client,
                use_llm=self.use_llm,
            )
            agents.append(agent)
        return agents
