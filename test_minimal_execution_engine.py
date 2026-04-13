from core.task4_mappers import build_sim_execution_spec
from run_test_pipeline_force_deepseek import run_pipeline
from simulation.minimal_execution_engine import MinimalExecutionEngine


if __name__ == "__main__":
    result = run_pipeline()
    if not result.get("opportunities") or not result.get("action_plans"):
        raise SystemExit("pipeline did not produce opportunity/action plan")

    opportunity = result["opportunities"][0]
    action_plan = result["action_plans"][0]
    spec = build_sim_execution_spec(opportunity, action_plan)

    prices = [100, 100.8, 101.6, 103.0, 104.2, 103.5, 105.1, 106.8, 108.4, 109.5]
    engine = MinimalExecutionEngine()
    sim_result = engine.run(spec, prices=prices, initial_capital=100000)

    print("SIM_RESULT=", sim_result.result_id, sim_result.instrument, round(sim_result.realized_pnl_pct, 4))
    print("FILL_COUNT=", len(sim_result.fills), "EXIT=", sim_result.exit_reason)
    print("MAX_DRAWDOWN=", round(sim_result.max_drawdown_pct, 4), "REVIEW_TRIGGERED=", sim_result.review_triggered)
