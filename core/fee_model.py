"""
core/fee_model.py — 全局手续费/滑点模型

M7 回测引擎和 M9 模拟盘共享同一套费率参数，
避免费率不一致导致回测与模拟盘结果偏差。

费率依据：
  佣金：万三（买卖均收），最低 5 元
  印花税：千一（仅卖出时收取）
  滑点：万五（买卖均计）
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeeModel:
    """手续费/滑点模型"""

    commission_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    slippage_pct: float = 0.0005
    min_commission: float = 5.0

    def buy_cost(self, notional: float) -> float:
        """买入成本 = 佣金 + 滑点"""
        commission = max(notional * self.commission_rate, self.min_commission)
        slippage = notional * self.slippage_pct
        return commission + slippage

    def sell_cost(self, notional: float) -> float:
        """卖出成本 = 佣金 + 印花税 + 滑点"""
        commission = max(notional * self.commission_rate, self.min_commission)
        stamp_tax = notional * self.stamp_tax_rate
        slippage = notional * self.slippage_pct
        return commission + stamp_tax + slippage

    def round_trip_cost(self, buy_notional: float, sell_notional: float) -> float:
        """往返总成本"""
        return self.buy_cost(buy_notional) + self.sell_cost(sell_notional)

    def round_trip_cost_pct(self) -> float:
        """往返交易成本占成交额的比例（估算）"""
        return self.commission_rate * 2 + self.stamp_tax_rate + self.slippage_pct * 2

    def net_return_pct(self, gross_return_pct: float, buy_notional: float) -> float:
        """从毛收益率扣除往返成本后的净收益率"""
        sell_notional = buy_notional * (1 + gross_return_pct / 100)
        cost = self.round_trip_cost(buy_notional, sell_notional)
        net_pnl = buy_notional * gross_return_pct / 100 - cost
        return net_pnl / buy_notional * 100


DEFAULT_FEE_MODEL = FeeModel()
