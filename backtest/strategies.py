"""
backtest/strategies.py — MarketRadar 基础策略定义

策略作为参数集合传入 StrategyBacktester，不含 Python 逻辑，
纯粹由「入场规则 + 止损 + 止盈 + 持仓上限」描述。

三个基础策略：
  1. MacroMomentum  — 宏观信号动量跟随（降准/刺激/货币政策）
  2. PolicyBreakout — 政策信号突破（财政/产业/监管政策）
  3. ComboFilter    — 多信号组合过滤（宏观+资金流双确认）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Strategy:
    """
    策略参数定义。

    signal_types:       触发该策略的信号类型列表
    signal_types_require_all: True=所有类型都需要出现（AND），False=任意一个（OR）
    min_intensity:      信号强度下限（1-10）
    min_confidence:     信号置信度下限（1-10）
    allowed_directions: 允许入场的方向（BULLISH/BEARISH/NEUTRAL）
    entry_timing:       入场时机 "T+1_open"（次日开盘）| "T+1_close"（次日收盘）
    stop_loss_pct:      止损幅度（相对入场价，如 0.05 = 5%）
    take_profit_pct:    止盈幅度（None = 不设上限）
    max_holding_days:   最大持仓天数（超过则强平）
    allowed_horizons:   允许的信号时效（None = 不限）
    allowed_markets:    允许的市场（None = 不限）
    """
    name: str
    description: str
    signal_types: List[str]
    signal_types_require_all: bool = False    # False = 任意一个信号类型匹配即可入场
    min_intensity: float = 6.0
    min_confidence: float = 5.0
    allowed_directions: List[str] = field(default_factory=lambda: ["BULLISH"])
    entry_timing: str = "T+1_open"
    stop_loss_pct: float = 0.05
    take_profit_pct: Optional[float] = 0.15
    max_holding_days: int = 30
    allowed_horizons: Optional[List[str]] = None    # None = 不限
    allowed_markets: Optional[List[str]] = None     # None = 不限

    def matches_signal(self, signal_type: str, intensity: float, confidence: float,
                       direction: str, horizon: str = "", market: str = "") -> bool:
        """判断一条信号是否符合该策略的入场条件"""
        if signal_type not in self.signal_types:
            return False
        if intensity < self.min_intensity:
            return False
        if confidence < self.min_confidence:
            return False
        if direction not in self.allowed_directions:
            return False
        if self.allowed_horizons and horizon and horizon not in self.allowed_horizons:
            return False
        if self.allowed_markets and market and market not in self.allowed_markets:
            return False
        return True


# ─────────────────────────────────────────────────────────────
# 策略注册表
# ─────────────────────────────────────────────────────────────

STRATEGIES: dict[str, Strategy] = {}


def register(s: Strategy):
    STRATEGIES[s.name] = s
    return s


# ── 策略1：MacroMomentum ─────────────────────────────────────
# 逻辑：宏观层面出现强力货币/财政信号（如降准、降息、国债扩张），
#       宽松货币周期往往驱动指数级别行情，用宽止盈（20%）+中等止损（5%）
#       捕捉系统性上涨，持有 30 天给行情足够空间。
register(Strategy(
    name="MacroMomentum",
    description=(
        "宏观动量策略：货币/财政政策宽松信号触发后，T+1 开盘买入沪深宽基 ETF。"
        "止损 5%，止盈 20%，最多持有 30 天。适合捕捉政策宽松期的系统性行情。"
    ),
    signal_types=["macro"],
    min_intensity=6.0,
    min_confidence=5.0,
    allowed_directions=["BULLISH"],
    entry_timing="T+1_open",
    stop_loss_pct=0.05,
    take_profit_pct=0.20,
    max_holding_days=30,
    allowed_horizons=["short", "medium"],
    allowed_markets=["A_SHARE", "HK"],
))


# ── 策略2：PolicyBreakout ────────────────────────────────────
# 逻辑：产业政策/监管政策发布后往往带来 1-2 周的主题行情，
#       但持续性不稳定。用更紧的止损（3%）和更近的止盈（10%），
#       快进快出，降低持仓风险。
register(Strategy(
    name="PolicyBreakout",
    description=(
        "政策突破策略：产业/监管政策信号后，T+1 开盘入场，"
        "止损 3%，止盈 10%，最多持有 15 天。适合主题政策短线行情。"
    ),
    signal_types=["policy", "industry"],
    signal_types_require_all=False,
    min_intensity=7.0,      # 要求更强的信号（政策解读噪音多）
    min_confidence=6.0,
    allowed_directions=["BULLISH"],
    entry_timing="T+1_open",
    stop_loss_pct=0.03,
    take_profit_pct=0.10,
    max_holding_days=15,
    allowed_markets=["A_SHARE"],
))


# ── 策略3：ComboFilter ───────────────────────────────────────
# 逻辑：同时要求宏观信号 + 资金流信号（双重确认），
#       过滤掉"政策出来但资金没跟上"的陷阱行情。
#       因为过滤条件更严，允许更宽的止损（7%）和更高的止盈（25%），
#       持有 45 天给行情完整展开空间。
register(Strategy(
    name="ComboFilter",
    description=(
        "组合过滤策略：要求宏观信号 + 资金流信号双重确认后入场。"
        "止损 7%，止盈 25%，最多持有 45 天。信号质量高，持仓时间长，"
        "适合捕捉资金驱动的大级别行情。"
    ),
    signal_types=["macro", "capital_flow"],
    signal_types_require_all=True,    # 两种信号都要出现
    min_intensity=6.0,
    min_confidence=5.5,
    allowed_directions=["BULLISH"],
    entry_timing="T+1_open",
    stop_loss_pct=0.07,
    take_profit_pct=0.25,
    max_holding_days=45,
    allowed_horizons=["short", "medium", "long"],
    allowed_markets=["A_SHARE", "HK"],
))
