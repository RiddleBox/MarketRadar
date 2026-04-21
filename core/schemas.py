"""
core/schemas.py — MarketRadar 全局数据模型

所有模块共享的 Pydantic v2 数据模型定义。
这是整个系统的"语言基础"，修改此文件会影响所有模块。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================
# Enums
# ============================================================

class Market(str, Enum):
    """市场标识"""
    A_SHARE = "A_SHARE"       # A股（沪深京）
    HK = "HK"                  # 港股（香港联交所）
    US = "US"                  # 美股（纽约/纳斯达克）
    A_FUTURES = "A_FUTURES"   # A股期货
    HK_FUTURES = "HK_FUTURES" # 港股期货
    US_FUTURES = "US_FUTURES" # 美股期货


class InstrumentType(str, Enum):
    """标的类型"""
    STOCK = "STOCK"       # 股票
    ETF = "ETF"           # ETF基金
    FUTURES = "FUTURES"   # 期货
    OPTIONS = "OPTIONS"   # 期权
    INDEX = "INDEX"       # 指数
    BOND = "BOND"         # 债券


class SignalType(str, Enum):
    """信号类型"""
    MACRO = "macro"                   # 宏观经济信号
    INDUSTRY = "industry"             # 行业层面信号
    CAPITAL_FLOW = "capital_flow"     # 资金流动信号
    TECHNICAL = "technical"           # 技术面信号
    EVENT_DRIVEN = "event_driven"     # 事件驱动信号
    POLICY = "policy"                 # 政策面信号
    SENTIMENT = "sentiment"           # 情绪面信号（预留给 MarketSentinel）


class SourceType(str, Enum):
    """信号来源类型"""
    NEWS = "news"                     # 新闻资讯
    RESEARCH_REPORT = "research_report"  # 研究报告
    OFFICIAL_ANNOUNCEMENT = "official_announcement"  # 官方公告
    MARKET_DATA = "market_data"       # 市场数据
    POLICY_DOCUMENT = "policy_document"  # 政策文件
    SOCIAL_MEDIA = "social_media"     # 社交媒体（主要给 MarketSentinel）
    MANUAL_INPUT = "manual_input"     # 人工输入


class Direction(str, Enum):
    """信号/机会方向"""
    BULLISH = "BULLISH"       # 看多
    BEARISH = "BEARISH"       # 看空
    NEUTRAL = "NEUTRAL"       # 中性
    UNCERTAIN = "UNCERTAIN"   # 不确定


class TimeHorizon(str, Enum):
    """时间维度"""
    SHORT = "SHORT"     # 短期（日/周，1d~4w）
    MEDIUM = "MEDIUM"   # 中期（月/季，1m~3m）
    LONG = "LONG"       # 长期（年+，6m~3y）


class PriorityLevel(str, Enum):
    """机会优先级"""
    WATCH = "watch"         # 关注：值得持续追踪，暂不行动
    RESEARCH = "research"   # 研究：需要深入研究后决策
    POSITION = "position"   # 建仓：可以按计划建立仓位
    URGENT = "urgent"       # 紧急：时间窗口极短，需立即决策


class PositionStatus(str, Enum):
    """持仓状态"""
    OPEN = "open"                   # 开仓中
    PARTIAL_CLOSE = "partial_close" # 部分平仓
    CLOSED = "closed"               # 已全部平仓
    STOP_LOSS = "stop_loss"         # 止损平仓
    TAKE_PROFIT = "take_profit"     # 止盈平仓
    EXPIRED = "expired"             # 到期/时间窗口结束


class ActionType(str, Enum):
    """行动类型"""
    BUY = "buy"                     # 买入/做多
    SELL = "sell"                   # 卖出/做空
    ADD = "add"                     # 加仓
    REDUCE = "reduce"               # 减仓
    CLOSE = "close"                 # 平仓
    WATCH = "watch"                 # 观察，暂不操作
    HEDGE = "hedge"                 # 对冲


# ============================================================
# Core Signal Models
# ============================================================

class SignalLogicFrame(BaseModel):
    """
    信号的逻辑框架。
    描述"什么变了"、"变化方向"和"影响什么"，
    是 MarketSignal 的结构化推理骨架。
    """
    what_changed: str = Field(
        ...,
        description="客观描述发生了什么变化。必须是已发生的事实，不是预测。"
                    "例：'央行将存款准备金率下调0.5个百分点至6.0%'"
    )
    change_direction: Direction = Field(
        ...,
        description="这个变化对被影响标的的方向性影响"
    )
    affects: List[str] = Field(
        ...,
        min_length=1,
        description="受影响的市场/行业/标的列表，用具体名称描述。"
                    "例：['银行股', '地产股', '债券市场']"
    )


class MarketSignal(BaseModel):
    """
    市场信号 — M1 的核心输出单元。

    代表一个从原始文本中提取的、结构化的市场事件信号。
    每个 MarketSignal 描述一个已经发生的客观变化及其市场含义。
    """
    signal_id: str = Field(
        default_factory=lambda: f"sig_{uuid.uuid4().hex[:12]}",
        description="信号唯一标识符"
    )
    signal_type: SignalType = Field(..., description="信号类型分类")
    signal_label: str = Field(
        ...,
        max_length=100,
        description="简短的信号标签，20字以内的中文描述。"
                    "例：'央行降准释放长期流动性'"
    )
    description: str = Field(
        ...,
        description="信号的完整客观描述，包含所有关键数据和背景信息"
    )
    evidence_text: str = Field(
        ...,
        description="支撑该信号的原始证据文本片段，直接引用来源内容"
    )

    # 市场相关性
    affected_markets: List[Market] = Field(
        ...,
        min_length=1,
        description="该信号直接影响的市场列表"
    )
    affected_instruments: List[str] = Field(
        default_factory=list,
        description="该信号直接影响的具体标的代码或名称列表。"
                    "可为空（当信号是宏观/行业层面，无法落实到具体标的时）"
    )

    # 方向和时间
    signal_direction: Direction = Field(
        ...,
        description="该信号对受影响市场/标的的整体方向性影响"
    )
    event_time: datetime = Field(
        ...,
        description="信号事件发生的时间（尽量精确到小时）"
    )
    collected_time: datetime = Field(
        default_factory=datetime.now,
        description="信号被系统采集/处理的时间"
    )
    time_horizon: TimeHorizon = Field(
        ...,
        description="该信号的预期作用时间维度"
    )

    # 评分体系（1-10分）
    intensity_score: int = Field(
        ...,
        ge=1, le=10,
        description="信号强度：变化的幅度和重要性。"
                    "1=微弱变化，5=显著变化，10=历史级别变化"
    )
    confidence_score: int = Field(
        ...,
        ge=1, le=10,
        description="信号置信度：来源可靠性和信息确定性。"
                    "1=传言未经证实，5=可信来源，10=官方权威发布"
    )
    timeliness_score: int = Field(
        ...,
        ge=1, le=10,
        description="时效性：信号的新鲜程度和市场已反应程度。"
                    "1=已充分定价，5=市场部分反应，10=刚刚发生尚未反应"
    )

    # 来源信息
    source_type: SourceType = Field(..., description="信号来源类型")
    source_ref: str = Field(
        ...,
        description="来源引用，可以是URL、文章标题、报告名称等"
    )

    # 结构化逻辑
    logic_frame: SignalLogicFrame = Field(
        ...,
        description="信号的结构化逻辑框架"
    )

    # 批次管理
    batch_id: Optional[str] = Field(
        default=None,
        description="所属处理批次ID，用于追踪和管理一批同时处理的信号"
    )

    @field_validator("intensity_score", "confidence_score", "timeliness_score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError(f"Score must be between 1 and 10, got {v}")
        return v

    def composite_score(self) -> float:
        """
        计算信号综合得分。
        加权平均：强度40% + 置信度40% + 时效性20%
        """
        return (
            self.intensity_score * 0.4
            + self.confidence_score * 0.4
            + self.timeliness_score * 0.2
        )


# ============================================================
# Opportunity Models
# ============================================================

class TimeWindow(BaseModel):
    """机会时间窗口"""
    start: datetime = Field(..., description="机会开始时间（最早可入场时间）")
    end: datetime = Field(..., description="机会结束时间（最晚需要决策/退出的时间）")
    confidence_level: float = Field(
        ...,
        ge=0.0, le=1.0,
        description="时间窗口判断的置信度，0.0~1.0。"
                    "0.3=时间窗口模糊，0.7=较为确定，1.0=窗口非常明确"
    )

    @model_validator(mode="after")
    def validate_time_order(self) -> "TimeWindow":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class OpportunityScore(BaseModel):
    """机会评分卡。用于将 M3 的判断拆解为可解释的多维评分。"""
    catalyst_strength: int = Field(..., ge=1, le=10, description="催化剂强度，1-10")
    timeliness: int = Field(..., ge=1, le=10, description="时效性，1-10")
    market_confirmation: int = Field(..., ge=1, le=10, description="市场确认度，1-10")
    tradability: int = Field(..., ge=1, le=10, description="可交易性，1-10")
    risk_clarity: int = Field(..., ge=1, le=10, description="风险边界清晰度，1-10")
    consensus_gap: int = Field(..., ge=1, le=10, description="预期差大小，1-10")
    signal_consistency: int = Field(..., ge=1, le=10, description="信号一致性，1-10")
    overall_score: float = Field(..., ge=0.0, le=10.0, description="综合得分，0-10")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="机会判断置信度，0-1")
    execution_readiness: float = Field(..., ge=0.0, le=1.0, description="执行就绪度，0-1")


class OpportunityObject(BaseModel):
    """
    市场机会对象 — M3 的核心输出单元。

    代表一个经过 M3 判断认为值得关注的市场机会。
    由多个 MarketSignal 组合推理而来，包含完整的机会描述、
    行动建议方向和风险警示。
    """
    opportunity_id: str = Field(
        default_factory=lambda: f"opp_{uuid.uuid4().hex[:12]}",
        description="机会唯一标识符"
    )
    opportunity_title: str = Field(
        ...,
        max_length=100,
        description="机会标题，30字以内，清晰描述机会本质。"
                    "例：'利率下行周期中高股息红利资产重估机会'"
    )
    opportunity_thesis: str = Field(
        ...,
        description="机会的核心投资逻辑，完整阐述为什么这是一个机会，"
                    "包括：催化剂、逻辑链条、预期收益来源"
    )

    # 市场和标的
    target_markets: List[Market] = Field(
        ...,
        min_length=1,
        description="机会所在的目标市场"
    )
    target_instruments: List[str] = Field(
        default_factory=list,
        description="具体的目标标的代码或名称（可为空，等待进一步研究确定）"
    )
    trade_direction: Direction = Field(
        ...,
        description="机会的交易方向（BULLISH=做多，BEARISH=做空）"
    )
    instrument_types: List[InstrumentType] = Field(
        ...,
        min_length=1,
        description="建议的交易标的类型（股票/ETF/期货等）"
    )

    # 时间窗口
    opportunity_window: TimeWindow = Field(
        ...,
        description="机会的时间窗口，定义入场和退出的时间边界"
    )

    # 核心逻辑
    why_now: str = Field(
        ...,
        description="为什么是现在？阐述机会的时效性，说明此刻入场的理由"
    )

    # 信号关联
    related_signals: List[str] = Field(
        ...,
        min_length=1,
        description="支撑该机会的相关信号ID列表"
    )
    supporting_evidence: List[str] = Field(
        ...,
        min_length=1,
        description="支持这个机会成立的论据列表"
    )
    counter_evidence: List[str] = Field(
        default_factory=list,
        description="反对这个机会或需要警惕的反向证据"
    )
    key_assumptions: List[str] = Field(
        ...,
        min_length=1,
        description="该机会成立所依赖的关键假设。假设被打破则机会失效。"
    )
    uncertainty_map: List[str] = Field(
        ...,
        min_length=1,
        description="主要不确定性来源，按重要程度排列"
    )

    # 决策参数
    priority_level: PriorityLevel = Field(
        ...,
        description="机会优先级，决定行动紧迫性"
    )
    opportunity_score: OpportunityScore = Field(
        ...,
        description="机会评分卡，用于解释机会为何成立以及强弱程度"
    )
    risk_reward_profile: str = Field(
        ...,
        description="风险收益特征描述，定性说明潜在盈利空间和可能损失。"
                    "例：'潜在收益20-30%，止损位明确，风险收益比约3:1'"
    )
    next_validation_questions: List[str] = Field(
        ...,
        min_length=1,
        description="需要进一步验证的问题列表，指导下一步研究方向"
    )
    invalidation_conditions: List[str] = Field(
        default_factory=list,
        description="机会失效条件。任一关键条件被触发时，需重新评估或退出。"
    )
    must_watch_indicators: List[str] = Field(
        default_factory=list,
        description="必须持续跟踪的验证指标或观测变量"
    )
    kill_switch_signals: List[str] = Field(
        default_factory=list,
        description="一旦出现就应快速放弃该机会的危险信号"
    )

    # 警告
    warnings: Optional[List[str]] = Field(
        default=None,
        description="特别警示事项，如流动性风险、黑天鹅风险等"
    )

    # 元数据
    judgment_version: str = Field(
        default="v1",
        description="判断版本号，用于追踪 M3 逻辑的迭代"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="机会创建时间"
    )
    batch_id: str = Field(
        ...,
        description="所属处理批次ID"
    )


# ============================================================
# Action Plan Models
# ============================================================

class StopLossConfig(BaseModel):
    """止损配置"""
    stop_loss_type: str = Field(
        ...,
        description="止损类型：price（绝对价格）/ percent（百分比）/ atr（ATR倍数）"
    )
    stop_loss_value: float = Field(
        ...,
        description="止损值，根据类型的含义不同：价格/百分比/ATR倍数"
    )
    stop_loss_price: Optional[float] = Field(
        default=None,
        description="具体止损价格（如果已知入场价则可以计算）"
    )
    hard_stop: bool = Field(
        default=True,
        description="是否为硬止损（到达即平仓）而非软止损（参考信号）"
    )
    notes: Optional[str] = Field(
        default=None,
        description="止损逻辑说明"
    )


class TakeProfitConfig(BaseModel):
    """止盈配置"""
    take_profit_type: str = Field(
        ...,
        description="止盈类型：price（绝对价格）/ percent（百分比）/ trailing（移动止盈）"
    )
    take_profit_value: float = Field(
        ...,
        description="止盈值，根据类型不同含义不同"
    )
    take_profit_price: Optional[float] = Field(
        default=None,
        description="具体止盈价格"
    )
    partial_take_profit: bool = Field(
        default=True,
        description="是否分批止盈（建议分批，保留底仓享受趋势）"
    )
    partial_ratio: float = Field(
        default=0.5,
        ge=0.1, le=1.0,
        description="第一次止盈的仓位比例，默认50%"
    )
    notes: Optional[str] = Field(default=None)


class PositionSizing(BaseModel):
    """仓位配置"""
    suggested_allocation: str = Field(
        ...,
        description="建议仓位占总资金的比例描述。例：'5-8%'"
    )
    max_allocation: str = Field(
        ...,
        description="最大仓位上限描述。例：'不超过10%'"
    )
    sizing_rationale: str = Field(
        ...,
        description="仓位大小的理由说明"
    )
    suggested_allocation_pct: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="建议仓位占总资金比例 (0.05 = 5%)"
    )
    max_allocation_pct: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="最大仓位占比 (0.10 = 10%)"
    )


class ActionPhase(BaseModel):
    """行动阶段"""
    phase_name: str = Field(..., description="阶段名称，例：'第一批建仓'")
    action_type: ActionType = Field(..., description="行动类型")
    timing_description: str = Field(
        ...,
        description="操作时机描述。例：'在指数回踩5日线时分批买入'"
    )
    allocation_ratio: float = Field(
        ...,
        ge=0.0, le=1.0,
        description="该阶段占总计划仓位的比例，所有阶段之和应为1.0"
    )
    price_range: Optional[str] = Field(
        default=None,
        description="建议操作的价格区间描述"
    )
    trigger_condition: Optional[str] = Field(
        default=None,
        description="触发该阶段行动的条件（可选，未满足条件则等待）"
    )


class ActionPlan(BaseModel):
    """
    行动计划 — M4 的核心输出单元。

    为一个 OpportunityObject 设计的具体、可执行的行动框架。
    在进场前就明确止损和止盈，是纪律性交易的基础。
    """
    plan_id: str = Field(
        default_factory=lambda: f"plan_{uuid.uuid4().hex[:12]}",
        description="行动计划唯一标识符"
    )
    opportunity_id: str = Field(
        ...,
        description="对应的机会ID"
    )
    plan_summary: str = Field(
        ...,
        description="行动计划总结，一段话描述整体操作思路"
    )

    # 标的信息
    primary_instruments: List[str] = Field(
        ...,
        min_length=1,
        description="主要操作标的（优先级排序）"
    )
    instrument_type: InstrumentType = Field(
        ...,
        description="主要标的类型"
    )
    direction: Direction = Field(
        ...,
        description="交易方向，从 OpportunityObject.trade_direction 传入"
    )
    market: Market = Field(
        default=Market.A_SHARE,
        description="目标市场，从 OpportunityObject.target_markets 传入"
    )

    # 核心配置
    stop_loss: StopLossConfig = Field(..., description="止损配置")
    take_profit: TakeProfitConfig = Field(..., description="止盈配置")
    position_sizing: PositionSizing = Field(..., description="仓位配置")

    # 分阶段行动
    phases: List[ActionPhase] = Field(
        ...,
        min_length=1,
        description="分阶段行动计划，按顺序执行"
    )

    # 时间管理
    valid_until: datetime = Field(
        ...,
        description="行动计划有效期，过期后需要重新评估"
    )
    review_triggers: List[str] = Field(
        ...,
        min_length=1,
        description="需要重新审视行动计划的触发条件。例：'如果30日内未触发入场则放弃'"
    )

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    opportunity_priority: PriorityLevel = Field(
        ...,
        description="对应机会的优先级（从 OpportunityObject 复制）"
    )


# ============================================================
# Position Models
# ============================================================

class BacktestTask(BaseModel):
    """回测任务定义。由 OpportunityObject 映射得到，供回测系统消费。"""
    task_id: str = Field(
        default_factory=lambda: f"bt_{uuid.uuid4().hex[:12]}",
        description="回测任务唯一标识符"
    )
    opportunity_id: str = Field(..., description="对应的机会ID")
    task_type: str = Field(default="event", description="回测任务类型：event/trend/regime/basket")
    market: Market = Field(..., description="目标市场")
    instrument_candidates: List[str] = Field(default_factory=list, description="候选回测标的")
    instrument_type: InstrumentType = Field(..., description="主要标的类型")
    direction: Direction = Field(..., description="回测方向")
    event_start: datetime = Field(..., description="回测事件起始时间")
    event_end: datetime = Field(..., description="回测事件结束时间")
    entry_rules: List[str] = Field(default_factory=list, description="入场规则说明")
    exit_rules: List[str] = Field(default_factory=list, description="退出规则说明")
    holding_period_grid: List[int] = Field(default_factory=lambda: [1, 3, 5, 10], description="持有期扫描窗口（交易日）")
    risk_budget_pct: float = Field(..., ge=0.0, le=1.0, description="风险预算占总资金比例")
    stop_loss_template: Optional[dict] = Field(default=None, description="止损模板")
    take_profit_template: Optional[dict] = Field(default=None, description="止盈模板")
    phase_template: List[dict] = Field(default_factory=list, description="分阶段执行模板")
    evaluation_metrics: List[str] = Field(default_factory=lambda: ["return", "max_drawdown", "win_rate", "profit_loss_ratio"], description="评估指标")
    metadata: dict = Field(default_factory=dict, description="附加元数据")


class SimulatedExecutionSpec(BaseModel):
    """模拟执行规格。由 ActionPlan 映射得到，供模拟盘系统消费。"""
    spec_id: str = Field(
        default_factory=lambda: f"sim_{uuid.uuid4().hex[:12]}",
        description="模拟执行规格唯一标识符"
    )
    plan_id: str = Field(..., description="对应的行动计划ID")
    opportunity_id: str = Field(..., description="对应的机会ID")
    market: Optional[Market] = Field(default=None, description="目标市场")
    instrument: str = Field(..., description="主要模拟执行标的")
    direction: Direction = Field(..., description="执行方向")
    entry_phases: List[ActionPhase] = Field(default_factory=list, description="分阶段执行计划")
    stop_loss_rule: StopLossConfig = Field(..., description="止损规则")
    take_profit_rule: TakeProfitConfig = Field(..., description="止盈规则")
    max_position_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="最大仓位比例")
    order_constraints: dict = Field(default_factory=dict, description="下单约束")
    slippage_model: dict = Field(default_factory=dict, description="滑点模型")
    fee_model: dict = Field(default_factory=dict, description="手续费模型")
    liquidity_constraints: dict = Field(default_factory=dict, description="流动性约束")
    expiry_time: datetime = Field(..., description="规格过期时间")
    review_triggers: List[str] = Field(default_factory=list, description="复核触发条件")
    metadata: dict = Field(default_factory=dict, description="附加元数据")


class BacktestRunResult(BaseModel):
    """单次回测运行结果。"""
    run_id: str = Field(
        default_factory=lambda: f"btr_{uuid.uuid4().hex[:12]}",
        description="回测运行唯一标识符"
    )
    task_id: str = Field(..., description="对应的回测任务ID")
    instrument: str = Field(..., description="执行回测的标的")
    holding_period_days: int = Field(..., ge=1, description="持有期（交易日）")
    entry_price: float = Field(..., gt=0, description="入场价格")
    exit_price: float = Field(..., gt=0, description="出场价格")
    gross_return_pct: float = Field(..., description="毛收益率")
    net_return_pct: float = Field(..., description="净收益率（扣成本后）")
    max_drawdown_pct: float = Field(..., description="持有期最大回撤")
    stop_loss_hit: bool = Field(default=False, description="是否触发止损")
    take_profit_hit: bool = Field(default=False, description="是否触发止盈")
    bars_held: int = Field(..., ge=1, description="实际持有K线数")
    notes: Optional[str] = Field(default=None, description="运行备注")
    metadata: dict = Field(default_factory=dict, description="附加元数据")


class BacktestSummary(BaseModel):
    """回测任务的汇总结果。"""
    summary_id: str = Field(
        default_factory=lambda: f"bts_{uuid.uuid4().hex[:12]}",
        description="回测汇总唯一标识符"
    )
    task_id: str = Field(..., description="对应的回测任务ID")
    total_runs: int = Field(..., ge=0, description="总运行数")
    win_rate: float = Field(..., ge=0.0, le=1.0, description="胜率")
    avg_net_return_pct: float = Field(..., description="平均净收益率")
    avg_max_drawdown_pct: float = Field(..., description="平均最大回撤")
    best_run_net_return_pct: float = Field(..., description="最佳净收益率")
    worst_run_net_return_pct: float = Field(..., description="最差净收益率")
    by_holding_period: dict = Field(default_factory=dict, description="按持有期分组的统计")
    runs: List[BacktestRunResult] = Field(default_factory=list, description="单次回测结果列表")


class InstrumentBacktestComparison(BaseModel):
    """多标的回测对比结果。"""
    comparison_id: str = Field(
        default_factory=lambda: f"btc_{uuid.uuid4().hex[:12]}",
        description="多标的对比结果唯一标识符"
    )
    task_id: str = Field(..., description="对应回测任务ID")
    market: Market = Field(..., description="目标市场")
    best_instrument: Optional[str] = Field(default=None, description="表现最佳的标的")
    ranked_results: List[dict] = Field(default_factory=list, description="按净收益排序的结果摘要")
    summaries: List[BacktestSummary] = Field(default_factory=list, description="各标的回测汇总")


class SimulatedFill(BaseModel):
    """模拟成交记录。"""
    fill_id: str = Field(
        default_factory=lambda: f"fill_{uuid.uuid4().hex[:12]}",
        description="成交记录唯一标识符"
    )
    phase_name: str = Field(..., description="对应执行阶段名称")
    instrument: str = Field(..., description="成交标的")
    side: str = Field(..., description="成交方向：buy/sell")
    price: float = Field(..., gt=0, description="成交价格")
    allocation_ratio: float = Field(..., ge=0.0, le=1.0, description="该次成交对应仓位比例")
    notional: float = Field(..., ge=0.0, description="成交名义金额")
    fee_paid: float = Field(..., ge=0.0, description="手续费")
    slippage_paid: float = Field(..., ge=0.0, description="滑点成本")


class SimulatedExecutionResult(BaseModel):
    """模拟执行结果。"""
    result_id: str = Field(
        default_factory=lambda: f"simr_{uuid.uuid4().hex[:12]}",
        description="模拟执行结果唯一标识符"
    )
    spec_id: str = Field(..., description="对应的模拟执行规格ID")
    plan_id: str = Field(..., description="对应的行动计划ID")
    opportunity_id: str = Field(..., description="对应的机会ID")
    instrument: str = Field(..., description="执行标的")
    fills: List[SimulatedFill] = Field(default_factory=list, description="模拟成交明细")
    average_entry_price: Optional[float] = Field(default=None, gt=0, description="平均入场价")
    exit_price: Optional[float] = Field(default=None, gt=0, description="退出价格")
    exit_reason: Optional[str] = Field(default=None, description="退出原因")
    realized_pnl_pct: float = Field(..., description="已实现盈亏百分比")
    max_drawdown_pct: float = Field(..., description="模拟持有期间最大回撤")
    review_triggered: bool = Field(default=False, description="是否触发复核")
    notes: Optional[str] = Field(default=None, description="结果备注")
    metadata: dict = Field(default_factory=dict, description="附加元数据")


class PositionUpdate(BaseModel):
    """持仓更新记录"""
    position_id: str = Field(..., description="对应的持仓ID")
    update_time: datetime = Field(default_factory=datetime.now)
    current_price: float = Field(..., description="更新时的当前价格")
    unrealized_pnl: float = Field(..., description="未实现盈亏（当前价-成本价）×数量")
    unrealized_pnl_pct: float = Field(..., description="未实现盈亏百分比")
    stop_loss_price: Optional[float] = Field(default=None, description="当前止损价")
    take_profit_price: Optional[float] = Field(default=None, description="当前止盈价")
    notes: Optional[str] = Field(default=None)


class Position(BaseModel):
    """
    持仓记录 — M5 的核心数据单元。

    记录一个交易标的的完整持仓生命周期，从开仓到平仓。
    """
    position_id: str = Field(
        default_factory=lambda: f"pos_{uuid.uuid4().hex[:12]}",
        description="持仓唯一标识符"
    )
    plan_id: str = Field(..., description="对应的行动计划ID")
    opportunity_id: str = Field(..., description="对应的机会ID")

    # 标的信息
    instrument: str = Field(..., description="标的代码或名称")
    instrument_type: InstrumentType = Field(...)
    market: Market = Field(...)

    # 交易信息
    direction: Direction = Field(..., description="做多(BULLISH) 或做空(BEARISH)")
    entry_price: float = Field(..., description="入场价格（加权平均成本）")
    entry_time: datetime = Field(..., description="开仓时间")
    quantity: float = Field(..., description="持仓数量（股数/手数）")
    total_cost: float = Field(..., description="总成本（入场价×数量）")

    # 止损止盈
    stop_loss_price: float = Field(..., description="当前有效止损价")
    take_profit_price: Optional[float] = Field(default=None, description="目标止盈价")

    # 状态
    status: PositionStatus = Field(default=PositionStatus.OPEN)

    # 平仓信息（开仓时为空）
    exit_price: Optional[float] = Field(default=None, description="出场价格")
    exit_time: Optional[datetime] = Field(default=None, description="平仓时间")
    exit_reason: Optional[str] = Field(default=None, description="平仓原因")
    realized_pnl: Optional[float] = Field(default=None, description="已实现盈亏")
    realized_pnl_pct: Optional[float] = Field(default=None, description="已实现盈亏百分比")

    # 历史更新记录
    updates: List[PositionUpdate] = Field(
        default_factory=list,
        description="价格更新历史记录"
    )

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    notes: Optional[str] = Field(default=None, description="持仓备注")

    def current_pnl(self, current_price: float) -> float:
        """计算当前未实现盈亏"""
        if self.direction == Direction.BULLISH:
            return (current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - current_price) * self.quantity

    def current_pnl_pct(self, current_price: float) -> float:
        """计算当前未实现盈亏百分比"""
        if self.total_cost == 0:
            return 0.0
        return self.current_pnl(current_price) / self.total_cost * 100


# ============================================================
# MarketSentinel Integration (Reserved)
# ============================================================

class SentimentSignal(BaseModel):
    """
    情绪面信号 — 预留给 MarketSentinel 系统。

    MarketSentinel 负责从社交媒体、论坛、情绪指标中提取情绪信号，
    通过此模型与 MarketRadar 进行数据交换。
    M3 可以将 SentimentSignal 作为辅助输入，进行情绪-结构共振判断。
    """
    signal_id: str = Field(
        default_factory=lambda: f"sent_{uuid.uuid4().hex[:12]}"
    )
    source_system: str = Field(
        default="MarketSentinel",
        description="来源系统标识"
    )

    # 情绪数据
    sentiment_score: float = Field(
        ...,
        ge=-1.0, le=1.0,
        description="情绪得分：-1.0(极度恐惧) ~ 0(中性) ~ 1.0(极度贪婪)"
    )
    sentiment_label: str = Field(
        ...,
        description="情绪标签描述，例：'社交媒体看多情绪创月度新高'"
    )

    # 市场关联
    affected_markets: List[Market] = Field(...)
    related_instruments: List[str] = Field(default_factory=list)

    # 时间
    observed_time: datetime = Field(...)
    collected_time: datetime = Field(default_factory=datetime.now)

    # 来源
    source_platform: str = Field(
        ...,
        description="数据来源平台，例：'雪球'、'东方财富股吧'、'微博'"
    )
    sample_size: Optional[int] = Field(
        default=None,
        description="统计样本数量（如涉及统计汇总）"
    )

    # 辅助判断
    is_extreme: bool = Field(
        default=False,
        description="是否处于情绪极值区间（极度恐惧或极度贪婪），极值往往是反转信号"
    )
    batch_id: Optional[str] = Field(default=None)
