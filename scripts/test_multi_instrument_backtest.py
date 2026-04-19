from backtest.minimal_backtest_engine import MinimalBacktestEngine
from core.task4_mappers import build_backtest_task
from data.price_loader import PriceLoader
from run_test_pipeline_force_deepseek import run_pipeline


if __name__ == "__main__":
    result = run_pipeline()
    if not result.get("opportunities"):
        raise SystemExit("no opportunity produced")

    opportunity = result["opportunities"][0]
    task = build_backtest_task(opportunity)

    loader = PriceLoader()
    instruments = task.instrument_candidates[:3] if task.instrument_candidates else ["沪深300ETF", "上证50ETF", "创业板ETF"]
    price_map = loader.load_closes_for_instruments(instruments, frequency="daily")
    if not price_map:
        raise SystemExit("no local csv prices found for candidate instruments")

    engine = MinimalBacktestEngine()
    comparison = engine.compare_instruments(task, price_map=price_map)

    print("COMPARISON=", comparison.comparison_id, comparison.best_instrument)
    for item in comparison.ranked_results:
        print("RANK=", item["instrument"], round(item["avg_net_return_pct"], 4), round(item["win_rate"], 4))
