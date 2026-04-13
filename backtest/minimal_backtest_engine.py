"""Minimal backtest executor for Task 4.

This first-stage engine intentionally keeps assumptions simple:
- input price series is daily close only
- entry at first bar close
- exit by fixed holding period or template stop/take level
- metrics focus on return and max drawdown
"""

from __future__ import annotations

from statistics import mean
from typing import Iterable, List

from core.schemas import BacktestRunResult, BacktestSummary, BacktestTask, Direction, InstrumentBacktestComparison


class MinimalBacktestEngine:
    """A minimal executor that validates BacktestTask can be run end-to-end."""

    def run(self, task: BacktestTask, instrument: str, closes: Iterable[float]) -> BacktestSummary:
        prices = [float(x) for x in closes]
        if len(prices) < 2:
            raise ValueError("at least 2 close prices are required")

        runs: List[BacktestRunResult] = []
        for holding_days in task.holding_period_grid:
            if holding_days >= len(prices):
                continue
            runs.append(self._run_once(task, instrument, prices, holding_days))

        if not runs:
            raise ValueError("no valid holding periods for supplied price series")

        total_runs = len(runs)
        win_rate = sum(1 for r in runs if r.net_return_pct > 0) / total_runs
        avg_net_return_pct = mean(r.net_return_pct for r in runs)
        avg_max_drawdown_pct = mean(r.max_drawdown_pct for r in runs)
        best_run = max(runs, key=lambda r: r.net_return_pct)
        worst_run = min(runs, key=lambda r: r.net_return_pct)

        by_holding_period = {
            str(r.holding_period_days): {
                "net_return_pct": r.net_return_pct,
                "max_drawdown_pct": r.max_drawdown_pct,
                "stop_loss_hit": r.stop_loss_hit,
                "take_profit_hit": r.take_profit_hit,
            }
            for r in runs
        }

        return BacktestSummary(
            task_id=task.task_id,
            total_runs=total_runs,
            win_rate=win_rate,
            avg_net_return_pct=avg_net_return_pct,
            avg_max_drawdown_pct=avg_max_drawdown_pct,
            best_run_net_return_pct=best_run.net_return_pct,
            worst_run_net_return_pct=worst_run.net_return_pct,
            by_holding_period=by_holding_period,
            runs=runs,
        )

    def compare_instruments(self, task: BacktestTask, price_map: dict[str, Iterable[float]]) -> InstrumentBacktestComparison:
        summaries: List[BacktestSummary] = []
        ranked_results: List[dict] = []

        for instrument, closes in price_map.items():
            summary = self.run(task, instrument=instrument, closes=closes)
            summaries.append(summary)
            ranked_results.append({
                "instrument": instrument,
                "avg_net_return_pct": summary.avg_net_return_pct,
                "win_rate": summary.win_rate,
                "avg_max_drawdown_pct": summary.avg_max_drawdown_pct,
            })

        ranked_results.sort(key=lambda x: x["avg_net_return_pct"], reverse=True)
        best_instrument = ranked_results[0]["instrument"] if ranked_results else None

        return InstrumentBacktestComparison(
            task_id=task.task_id,
            market=task.market,
            best_instrument=best_instrument,
            ranked_results=ranked_results,
            summaries=summaries,
        )

    def _run_once(
        self,
        task: BacktestTask,
        instrument: str,
        prices: List[float],
        holding_days: int,
    ) -> BacktestRunResult:
        entry_price = prices[0]
        window = prices[: holding_days + 1]
        stop_loss_pct = self._template_value(task.stop_loss_template)
        take_profit_pct = self._template_value(task.take_profit_template)

        exit_idx = holding_days
        stop_loss_hit = False
        take_profit_hit = False

        for idx, price in enumerate(window[1:], start=1):
            ret_pct = self._calc_return_pct(task.direction, entry_price, price)
            if stop_loss_pct is not None and ret_pct <= -stop_loss_pct:
                exit_idx = idx
                stop_loss_hit = True
                break
            if take_profit_pct is not None and ret_pct >= take_profit_pct:
                exit_idx = idx
                take_profit_hit = True
                break

        exit_price = window[exit_idx]
        gross_return_pct = self._calc_return_pct(task.direction, entry_price, exit_price)
        fee_pct = 0.06
        slippage_pct = 0.05
        net_return_pct = gross_return_pct - fee_pct - slippage_pct
        max_drawdown_pct = self._max_drawdown_pct(task.direction, entry_price, window[: exit_idx + 1])

        return BacktestRunResult(
            task_id=task.task_id,
            instrument=instrument,
            holding_period_days=holding_days,
            entry_price=entry_price,
            exit_price=exit_price,
            gross_return_pct=gross_return_pct,
            net_return_pct=net_return_pct,
            max_drawdown_pct=max_drawdown_pct,
            stop_loss_hit=stop_loss_hit,
            take_profit_hit=take_profit_hit,
            bars_held=exit_idx + 1,
            metadata={
                "direction": task.direction.value,
                "risk_budget_pct": task.risk_budget_pct,
            },
        )

    @staticmethod
    def _template_value(template: dict | None) -> float | None:
        if not template:
            return None
        value = template.get("value")
        return float(value) if value is not None else None

    @staticmethod
    def _calc_return_pct(direction: Direction, entry: float, current: float) -> float:
        if entry == 0:
            return 0.0
        if direction == Direction.BULLISH:
            return (current - entry) / entry * 100
        return (entry - current) / entry * 100

    @staticmethod
    def _max_drawdown_pct(direction: Direction, entry: float, prices: List[float]) -> float:
        if direction == Direction.BULLISH:
            worst_price = min(prices)
            return min(0.0, (worst_price - entry) / entry * 100)
        worst_price = max(prices)
        return min(0.0, (entry - worst_price) / entry * 100)
