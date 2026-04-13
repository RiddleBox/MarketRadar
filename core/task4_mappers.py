"""Task 4 mappers: convert M3/M4 core objects into backtest/sim specs."""

from __future__ import annotations

from typing import Optional

import yaml
from pathlib import Path

from core.schemas import (
    ActionPlan,
    BacktestTask,
    Direction,
    OpportunityObject,
    SimulatedExecutionSpec,
)


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _load_yaml_config(filename: str) -> dict:
    path = CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


RISK_CONFIG = _load_yaml_config("risk_config.yaml")
EXECUTION_CONFIG = _load_yaml_config("execution_config.yaml")


def build_backtest_task(opportunity: OpportunityObject) -> BacktestTask:
    instrument_type = opportunity.instrument_types[0]
    phase_templates = EXECUTION_CONFIG.get("phase_templates", {})
    phase_template = (
        phase_templates.get(instrument_type.value, {}).get(opportunity.priority_level.value)
        or phase_templates.get("default", {}).get(opportunity.priority_level.value, [])
    )
    instrument_cfg = RISK_CONFIG.get("instrument_risk_overrides", {}).get(instrument_type.value, {})
    risk_budget_pct = float(
        RISK_CONFIG.get("priority_risk_budget_pct", {}).get(opportunity.priority_level.value, 0)
    ) / 100

    return BacktestTask(
        opportunity_id=opportunity.opportunity_id,
        task_type="event",
        market=opportunity.target_markets[0],
        instrument_candidates=opportunity.target_instruments,
        instrument_type=instrument_type,
        direction=opportunity.trade_direction,
        event_start=opportunity.opportunity_window.start,
        event_end=opportunity.opportunity_window.end,
        entry_rules=[
            opportunity.why_now,
            *opportunity.key_assumptions,
        ],
        exit_rules=[
            *opportunity.invalidation_conditions,
            *opportunity.kill_switch_signals,
        ],
        risk_budget_pct=risk_budget_pct,
        stop_loss_template={
            "type": EXECUTION_CONFIG.get("fallback_stop_loss", {}).get("type", "percent"),
            "value": instrument_cfg.get("preferred_stop_loss_pct", 5),
        },
        take_profit_template={
            "type": EXECUTION_CONFIG.get("fallback_take_profit", {}).get("type", "percent"),
            "value": instrument_cfg.get("preferred_take_profit_pct", 10),
        },
        phase_template=phase_template,
        metadata={
            "priority_level": opportunity.priority_level.value,
            "opportunity_score": opportunity.opportunity_score.model_dump(),
            "must_watch_indicators": opportunity.must_watch_indicators,
        },
    )


def _parse_allocation_percent(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    digits = "".join(ch for ch in text if (ch.isdigit() or ch == "."))
    if not digits:
        return None
    return float(digits) / 100


def build_sim_execution_spec(
    opportunity: OpportunityObject,
    action_plan: ActionPlan,
) -> SimulatedExecutionSpec:
    max_single_position_pct = float(RISK_CONFIG.get("global", {}).get("max_single_position_pct", 0)) / 100

    return SimulatedExecutionSpec(
        plan_id=action_plan.plan_id,
        opportunity_id=action_plan.opportunity_id,
        market=opportunity.target_markets[0] if opportunity.target_markets else None,
        instrument=(action_plan.primary_instruments[0] if action_plan.primary_instruments else "待定"),
        direction=opportunity.trade_direction if opportunity.trade_direction else Direction.BULLISH,
        entry_phases=action_plan.phases,
        stop_loss_rule=action_plan.stop_loss,
        take_profit_rule=action_plan.take_profit,
        max_position_pct=_parse_allocation_percent(action_plan.position_sizing.max_allocation) or max_single_position_pct,
        order_constraints={
            "instrument_type": action_plan.instrument_type.value,
            "priority": action_plan.opportunity_priority.value,
        },
        slippage_model={"mode": "fixed_bps", "value": 5},
        fee_model={"mode": "simple", "commission_bps": 3},
        liquidity_constraints={"min_fill_ratio": 0.8},
        expiry_time=action_plan.valid_until,
        review_triggers=action_plan.review_triggers,
        metadata={
            "plan_summary": action_plan.plan_summary,
            "suggested_allocation": action_plan.position_sizing.suggested_allocation,
        },
    )
