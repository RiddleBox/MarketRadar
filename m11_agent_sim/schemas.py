"""
m11_agent_sim/schemas.py — M11 核心数据结构

设计原则：
  - MarketInput     : 模拟的输入快照（信号 + 价格 + 情绪 + 时间）
  - AgentConfig     : 单个 Agent 的配置（类型、权重、序列位置）
  - AgentOutput     : 单个 Agent 的分析输出（方向 + 概率 + 置信度 + 理由）
  - SentimentDistribution : 整个 AgentNetwork 的综合输出
  - CalibrationScore : 历史回放的多维度评分
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
# 方向枚举（与 MarketSignal 保持一致）
# ─────────────────────────────────────────────────────────────

Direction = Literal["BULLISH", "BEARISH", "NEUTRAL"]


# ─────────────────────────────────────────────────────────────
# 输入
# ─────────────────────────────────────────────────────────────

class PriceContext(BaseModel):
    """价格上下文：近期行情数据"""
    instrument: str = ""
    current_price: float = 0.0
    price_5d_chg_pct: float = 0.0     # 5日涨跌幅
    price_20d_chg_pct: float = 0.0    # 20日涨跌幅
    volume_ratio: float = 1.0          # 量比（今日量/近5日均量）
    ma5: float = 0.0
    ma20: float = 0.0
    above_ma5: bool = True
    above_ma20: bool = True


class SentimentContext(BaseModel):
    """情绪上下文：M10 最新快照"""
    fear_greed_index: float = 50.0
    sentiment_label: str = "中性"
    northbound_flow: float = 0.0      # 北向资金净流入（亿元）
    advance_decline_ratio: float = 0.5  # 涨家/(涨家+跌家)
    weibo_sentiment: float = 0.0      # 微博情绪均值 [-1, 1]
    hot_sectors: List[str] = Field(default_factory=list)


class SignalContext(BaseModel):
    """信号上下文：来自 M1/M2 的近期信号摘要"""
    recent_signals: List[Dict[str, Any]] = Field(default_factory=list)
    dominant_signal_type: str = ""    # 最多的信号类型
    avg_intensity: float = 0.0
    avg_confidence: float = 0.0
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0


class MarketInput(BaseModel):
    """
    模拟输入快照 — AgentNetwork.run() 的入参

    包含一次模拟所需的全部市场信息：
    - 时间戳（用于历史回放时锚定日期）
    - 价格上下文
    - 情绪上下文
    - 信号上下文
    - 历史上下文（近期极端行情，供均值回归/止盈推理）
    - 原始事件描述（可选，用于 LLM prompt）
    """
    timestamp: datetime = Field(default_factory=datetime.now)
    market: str = "A_SHARE"           # "A_SHARE" | "HK" | "US"
    event_description: str = ""       # 触发本次模拟的事件描述（自然语言）
    price: PriceContext = Field(default_factory=PriceContext)
    sentiment: SentimentContext = Field(default_factory=SentimentContext)
    signals: SignalContext = Field(default_factory=SignalContext)
    recent_extreme_move: float = 0.0  # 近5日最大单日涨幅(正)/跌幅(负)，供止盈/恐慌推理
    days_since_extreme: int = 0        # 距离最近一次极端行情的天数
    extra: Dict[str, Any] = Field(default_factory=dict)  # 扩展字段


# ─────────────────────────────────────────────────────────────
# Agent 配置
# ─────────────────────────────────────────────────────────────

class AgentConfig(BaseModel):
    """
    单个 Agent 的配置

    weight       : 在最终聚合时的投票权重（0~1，所有 Agent 权重之和应为 1）
    sequence_pos : 在序列传导中的位置（0=最先，越大越后）
    enabled      : 是否参与本次模拟
    params       : Agent 特有参数（如技术面 Agent 的 MA 窗口）
    """
    agent_type: str                   # "policy" | "northbound" | "technical" | "sentiment" | "fundamental"
    name: str = ""
    weight: float = 0.2
    sequence_pos: int = 0
    enabled: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)


class NetworkConfig(BaseModel):
    """
    AgentNetwork 配置

    topology     : "sequential"（序列传导）| "graph"（图结构，Phase 2）
    agents       : Agent 列表，按 sequence_pos 排序后依次执行
    weight_matrix: 图结构的邻接权重（Phase 2 用，sequential 模式忽略）
                   格式：{from_agent: {to_agent: weight}}
    """
    market: str = "A_SHARE"
    topology: Literal["sequential", "graph"] = "sequential"
    agents: List[AgentConfig] = Field(default_factory=list)
    weight_matrix: Dict[str, Dict[str, float]] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# 输出
# ─────────────────────────────────────────────────────────────

class AgentOutput(BaseModel):
    """
    单个 Agent 的分析输出

    direction    : 看多/看空/中性
    bullish_prob : 上涨概率（0~1）
    bearish_prob : 下跌概率（0~1）
    neutral_prob : 震荡概率（0~1，三者之和 = 1）
    confidence   : 置信度（0~1，数据充分且逻辑清晰时高）
    intensity    : 情绪强度（0~10）
    reasoning    : LLM 给出的简要推理
    data_used    : 使用了哪些数据维度
    """
    agent_type: str
    agent_name: str = ""
    direction: Direction = "NEUTRAL"
    bullish_prob: float = 0.333
    bearish_prob: float = 0.333
    neutral_prob: float = 0.334
    confidence: float = 0.5
    intensity: float = 5.0
    reasoning: str = ""
    data_used: List[str] = Field(default_factory=list)

    def normalize_probs(self) -> "AgentOutput":
        """确保三个概率之和为 1"""
        total = self.bullish_prob + self.bearish_prob + self.neutral_prob
        if total > 0:
            self.bullish_prob /= total
            self.bearish_prob /= total
            self.neutral_prob /= total
        return self


class SentimentDistribution(BaseModel):
    """
    AgentNetwork 的综合输出 — 情绪概率分布

    这是 M11 对外的核心输出，不是点预测，而是概率分布：
    - 多方概率 / 空方概率 / 震荡概率
    - 置信区间（由各 Agent 置信度的加权方差推导）
    - 综合方向（概率最大的方向）
    - 情绪强度（加权平均）

    设计意图（D-03）：
      不追求价格曲线拟合，追求
      P(ΔPrice | S_模拟) ≈ P(ΔPrice | S_历史实测)
    """
    timestamp: datetime = Field(default_factory=datetime.now)
    market: str = "A_SHARE"
    event_description: str = ""

    # 核心概率分布
    bullish_prob: float = 0.333
    bearish_prob: float = 0.333
    neutral_prob: float = 0.334

    # 综合判断
    direction: Direction = "NEUTRAL"
    intensity: float = 5.0            # 0~10
    confidence: float = 0.5           # 0~1

    # 置信区间（95% CI）
    bullish_prob_ci_low: float = 0.0
    bullish_prob_ci_high: float = 1.0

    # 各 Agent 明细
    agent_outputs: List[AgentOutput] = Field(default_factory=list)

    # 元信息
    topology_used: str = "sequential"
    agents_count: int = 0
    simulation_ms: int = 0            # 模拟耗时（毫秒）
    no_trade: bool = False            # 置信度门控：低置信时标记不交易

    def summary(self) -> str:
        return (
            f"{self.direction} | "
            f"多{self.bullish_prob:.0%}/空{self.bearish_prob:.0%}/震{self.neutral_prob:.0%} "
            f"强度{self.intensity:.1f} 置信{self.confidence:.0%}"
        )


# ─────────────────────────────────────────────────────────────
# 历史校准
# ─────────────────────────────────────────────────────────────

class HistoricalEvent(BaseModel):
    """
    历史事件 — 校准数据集中的一个样本

    actual_direction   : 事件发生后实际的市场方向（从价格数据计算）
    actual_5d_return   : 事件后5日实际收益率
    actual_is_extreme  : 是否为历史极值点（大涨/大跌）
    """
    event_id: str
    date: str                          # "YYYY-MM-DD"
    description: str
    market_input: MarketInput
    actual_direction: Direction = "NEUTRAL"
    actual_5d_return: float = 0.0
    actual_is_extreme: bool = False


class CalibrationScore(BaseModel):
    """
    多维度校准评分（D-03）

    direction_accuracy   : 方向命中率（模拟方向 == 实际方向）
    prob_calibration_err : 概率校准误差（模拟上涨概率 vs 实际上涨频率）
    extreme_recall       : 极值识别召回率（历史极值点中被正确标记的比例）
    composite_score      : 加权综合分（0~100）

    选择性准确率（为胜率而交易，不为交易而交易）：
    selective_accuracy   : 仅在有方向判断（非NEUTRAL）时的命中率
    skip_rate            : 跳过率（系统输出NEUTRAL的比例，即不交易）
    """
    total_events: int = 0
    direction_hits: int = 0
    direction_accuracy: float = 0.0   # 目标 ≥ 70%

    prob_calibration_err: float = 0.0  # 越小越好，< 0.15 为合格
    extreme_recall: float = 0.0        # 目标 ≥ 60%

    composite_score: float = 0.0       # 加权综合分
    pass_threshold: bool = False       # 是否通过校准

    # 选择性准确率
    selective_accuracy: float = 0.0    # 有方向判断时的命中率
    selective_n: int = 0               # 有方向判断的事件数
    skip_rate: float = 0.0             # 跳过率（NEUTRAL比例）

    details: List[Dict[str, Any]] = Field(default_factory=list)  # 每个事件的明细


class ValidationCase(BaseModel):
    """单个历史事件的验证结果（事件 + 模拟输出 + 匹配判定）"""
    event_id: str
    date: str
    description: str
    actual_direction: Direction = "NEUTRAL"
    simulated_direction: Direction = "NEUTRAL"
    direction_match: bool = False
    actual_5d_return: float = 0.0
    simulated_bullish_prob: float = 0.0
    prob_error: float = 0.0
    simulated_intensity: float = 5.0
    simulated_confidence: float = 0.5


class CalibrationRun(BaseModel):
    """一次完整的校准运行记录"""
    run_id: str
    run_timestamp: datetime = Field(default_factory=datetime.now)
    market: str = "A_SHARE"
    topology: str = "sequential"
    n_events: int = 0
    score: CalibrationScore = Field(default_factory=CalibrationScore)
    cases: List[ValidationCase] = Field(default_factory=list)
