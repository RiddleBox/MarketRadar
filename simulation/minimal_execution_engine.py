"""Minimal execution simulator for Task 4.

This engine validates that SimulatedExecutionSpec can be consumed end-to-end.
It keeps assumptions intentionally simple and focuses on fill generation,
pnl accounting, and exit/review signalling.
"""

from __future__ import annotations

from typing import Iterable, List

from core.schemas import SimulatedExecutionResult, SimulatedExecutionSpec, SimulatedFill


class MinimalExecutionEngine:
    """A minimal simulator for ActionPlan-derived execution specs."""

    def run(self, spec: SimulatedExecutionSpec, prices: Iterable[float], initial_capital: float = 100000.0) -> SimulatedExecutionResult:
        series = [float(x) for x in prices]
        if len(series) < 2:
            raise ValueError("at least 2 prices are required")

        entry_price = series[0]
        fills: List[SimulatedFill] = []
        capital_limit = initial_capital * (spec.max_position_pct or 0.0)
        used_notional = 0.0

        for phase in spec.entry_phases:
            phase_notional = capital_limit * phase.allocation_ratio
            fee_paid = phase_notional * self._fee_rate(spec)
            slippage_paid = phase_notional * self._slippage_rate(spec)
            fills.append(
                SimulatedFill(
                    phase_name=phase.phase_name,
                    instrument=spec.instrument,
                    side=phase.action_type.value,
                    price=entry_price,
                    allocation_ratio=phase.allocation_ratio,
                    notional=phase_notional,
                    fee_paid=fee_paid,
                    slippage_paid=slippage_paid,
                )
            )
            used_notional += phase_notional

        avg_entry_price = entry_price if fills else None
        exit_price, exit_reason = self._resolve_exit(spec, series, entry_price)
        realized_pnl_pct = self._calc_return_pct(entry_price, exit_price, bullish=(spec.direction.value == "BULLISH"))
        realized_pnl_pct -= (self._fee_rate(spec) + self._slippage_rate(spec)) * 100
        max_drawdown_pct = self._max_drawdown_pct(series, entry_price, bullish=(spec.direction.value == "BULLISH"))
        review_triggered = len(series) > max(3, len(spec.entry_phases)) and not exit_reason.startswith("take_profit")

        return SimulatedExecutionResult(
            spec_id=spec.spec_id,
            plan_id=spec.plan_id,
            opportunity_id=spec.opportunity_id,
            instrument=spec.instrument,
            fills=fills,
            average_entry_price=avg_entry_price,
            exit_price=exit_price,
            exit_reason=exit_reason,
            realized_pnl_pct=realized_pnl_pct,
            max_drawdown_pct=max_drawdown_pct,
            review_triggered=review_triggered,
            metadata={
                "used_notional": used_notional,
                "review_triggers": spec.review_triggers,
            },
        )

    def _resolve_exit(self, spec: SimulatedExecutionSpec, prices: List[float], entry_price: float) -> tuple[float, str]:
        stop_loss_pct = float(spec.stop_loss_rule.stop_loss_value)
        take_profit_pct = float(spec.take_profit_rule.take_profit_value)
        bullish = spec.direction.value == "BULLISH"

        for idx, price in enumerate(prices[1:], start=1):
            ret_pct = self._calc_return_pct(entry_price, price, bullish=bullish)
            if spec.stop_loss_rule.stop_loss_type == "percent" and ret_pct <= -stop_loss_pct:
                return price, f"stop_loss_hit_t+{idx}"
            if spec.take_profit_rule.take_profit_type == "percent" and ret_pct >= take_profit_pct:
                return price, f"take_profit_hit_t+{idx}"

        return prices[-1], "expiry_or_series_end"

    @staticmethod
    def _fee_rate(spec: SimulatedExecutionSpec) -> float:
        commission_bps = float(spec.fee_model.get("commission_bps", 3))
        return commission_bps / 10000

    @staticmethod
    def _slippage_rate(spec: SimulatedExecutionSpec) -> float:
        value = float(spec.slippage_model.get("value", 5))
        return value / 10000

    @staticmethod
    def _calc_return_pct(entry_price: float, current_price: float, bullish: bool = True) -> float:
        if entry_price == 0:
            return 0.0
        if bullish:
            return (current_price - entry_price) / entry_price * 100
        return (entry_price - current_price) / entry_price * 100

    @staticmethod
    def _max_drawdown_pct(prices: List[float], entry_price: float, bullish: bool = True) -> float:
        if bullish:
            worst_price = min(prices)
            return min(0.0, (worst_price - entry_price) / entry_price * 100)
        worst_price = max(prices)
        return min(0.0, (entry_price - worst_price) / entry_price * 100)
