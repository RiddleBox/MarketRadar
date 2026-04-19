from core.task4_mappers import build_backtest_task, build_sim_execution_spec
from run_test_pipeline_force_deepseek import run_pipeline


if __name__ == "__main__":
    result = run_pipeline()
    if not result or not result.get("opportunities") or not result.get("action_plans"):
        raise SystemExit("pipeline did not produce opportunity/action plan")

    opportunity = result["opportunities"][0]
    action_plan = result["action_plans"][0]

    backtest_task = build_backtest_task(opportunity)
    sim_spec = build_sim_execution_spec(opportunity, action_plan)

    print("BACKTEST_TASK=", backtest_task.task_id, backtest_task.market, backtest_task.instrument_type)
    print("SIM_SPEC=", sim_spec.spec_id, sim_spec.instrument, sim_spec.max_position_pct)
    print("ENTRY_PHASES=", len(sim_spec.entry_phases))
