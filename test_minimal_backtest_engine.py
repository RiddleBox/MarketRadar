from backtest.minimal_backtest_engine import MinimalBacktestEngine
from core.task4_mappers import build_backtest_task
from run_test_pipeline_force_deepseek import run_pipeline


if __name__ == "__main__":
    result = run_pipeline()
    if not result.get("opportunities"):
        raise SystemExit("no opportunity produced")

    opportunity = result["opportunities"][0]
    task = build_backtest_task(opportunity)

    closes = [100, 101.5, 103.2, 102.8, 104.5, 106.0, 107.8, 106.9, 108.6, 110.2, 109.7]
    engine = MinimalBacktestEngine()
    summary = engine.run(task, instrument=task.instrument_candidates[0] if task.instrument_candidates else "TEST_ETF", closes=closes)

    print("BACKTEST_SUMMARY=", summary.summary_id, summary.total_runs, round(summary.win_rate, 4))
    print("AVG_NET_RETURN=", round(summary.avg_net_return_pct, 4))
    print("BEST/WORST=", round(summary.best_run_net_return_pct, 4), round(summary.worst_run_net_return_pct, 4))
    print("HOLDING_PERIOD_KEYS=", sorted(summary.by_holding_period.keys()))
