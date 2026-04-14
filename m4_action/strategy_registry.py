"""
m4_action/strategy_registry.py — M4 / backtest 共享策略语义最小注册表

当前目标：
- 提供最小共享 strategy identity / spec
- 不改变 M4 主链行为
- 不要求 M4 立即多策略输出
- 不替代 backtest 中更完整的 Strategy 参数对象
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class StrategySpec:
    """跨 M4 / backtest 共享的最小策略语义对象。"""

    name: str
    description: str
    style: str
    allowed_signal_types: List[str] = field(default_factory=list)
    allowed_directions: List[str] = field(default_factory=lambda: ["BULLISH"])
    allowed_markets: Optional[List[str]] = None
    allowed_horizons: Optional[List[str]] = None
    entry_timing: str = "T+1_open"
    risk_profile: Dict[str, float] = field(default_factory=dict)
    exit_profile: Dict[str, float] = field(default_factory=dict)


STRATEGY_REGISTRY: Dict[str, StrategySpec] = {
    "MacroMomentum": StrategySpec(
        name="MacroMomentum",
        description="宏观动量策略：货币/财政政策宽松信号触发后，T+1 开盘买入宽基 ETF。",
        style="macro_momentum",
        allowed_signal_types=["macro"],
        allowed_directions=["BULLISH"],
        allowed_markets=["A_SHARE", "HK"],
        allowed_horizons=["short", "medium"],
        entry_timing="T+1_open",
        risk_profile={"stop_loss_pct": 0.05, "max_holding_days": 30},
        exit_profile={"take_profit_pct": 0.20},
    ),
    "PolicyBreakout": StrategySpec(
        name="PolicyBreakout",
        description="政策突破策略：产业/监管政策信号后，T+1 开盘入场，适合主题短线行情。",
        style="policy_breakout",
        allowed_signal_types=["policy", "industry"],
        allowed_directions=["BULLISH"],
        allowed_markets=["A_SHARE"],
        entry_timing="T+1_open",
        risk_profile={"stop_loss_pct": 0.03, "max_holding_days": 15},
        exit_profile={"take_profit_pct": 0.10},
    ),
    "ComboFilter": StrategySpec(
        name="ComboFilter",
        description="组合过滤策略：要求宏观 + 资金流双确认，适合捕捉资金驱动的大级别行情。",
        style="combo_filter",
        allowed_signal_types=["macro", "capital_flow"],
        allowed_directions=["BULLISH"],
        allowed_markets=["A_SHARE", "HK"],
        allowed_horizons=["short", "medium", "long"],
        entry_timing="T+1_open",
        risk_profile={"stop_loss_pct": 0.07, "max_holding_days": 45},
        exit_profile={"take_profit_pct": 0.25},
    ),
}


def get_strategy_spec(name: str) -> Optional[StrategySpec]:
    return STRATEGY_REGISTRY.get(name)


def list_strategy_specs() -> List[StrategySpec]:
    return list(STRATEGY_REGISTRY.values())
