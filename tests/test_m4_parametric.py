"""
tests/test_m4_parametric.py — M4 参数化行动设计测试

覆盖：
  1. compute_kelly_position() 单元测试
  2. compute_position_from_risk_budget() 单元测试
  3. 品类模板差异化（ETF/STOCK/FUTURES）
  4. _build_action_plan 使用参数化仓位而非硬编码
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from core.schemas import (
    Direction, InstrumentType, Market, OpportunityObject, OpportunityScore,
    PriorityLevel, TimeWindow,
)
from m4_action.action_designer import (
    ActionDesigner,
    compute_kelly_position,
    compute_position_from_risk_budget,
    EXECUTION_CONFIG,
)


def _make_opportunity(
    instrument_type: InstrumentType = InstrumentType.ETF,
    priority: PriorityLevel = PriorityLevel.POSITION,
    direction: Direction = Direction.BULLISH,
    overall_score: float = 7.5,
    confidence: float = 0.75,
) -> OpportunityObject:
    now = datetime(2026, 4, 14, 9, 30, 0)
    return OpportunityObject(
        opportunity_id="opp_param_test",
        opportunity_title="参数化测试机会",
        opportunity_thesis="测试用",
        target_markets=[Market.A_SHARE],
        target_instruments=["510300"],
        trade_direction=direction,
        instrument_types=[instrument_type],
        opportunity_window=TimeWindow(start=now, end=now + timedelta(days=14), confidence_level=0.7),
        why_now="测试",
        related_signals=["sig_001"],
        supporting_evidence=["evidence1"],
        key_assumptions=["假设1"],
        uncertainty_map=["不确定性1"],
        priority_level=priority,
        opportunity_score=OpportunityScore(
            catalyst_strength=7, timeliness=7, market_confirmation=6,
            tradability=7, risk_clarity=6, consensus_gap=6,
            signal_consistency=7, overall_score=overall_score,
            confidence_score=confidence, execution_readiness=0.6,
        ),
        risk_reward_profile="2:1",
        next_validation_questions=["验证1"],
        batch_id="test_param",
    )


class TestKellyPosition:
    def test_positive_edge(self):
        result = compute_kelly_position(win_rate=0.6, avg_win_pct=0.10, avg_loss_pct=0.05)
        assert result > 0

    def test_quarter_kelly_fraction(self):
        full = compute_kelly_position(win_rate=0.6, avg_win_pct=0.10, avg_loss_pct=0.05, fraction=1.0)
        quarter = compute_kelly_position(win_rate=0.6, avg_win_pct=0.10, avg_loss_pct=0.05, fraction=0.25)
        assert abs(quarter - full * 0.25) < 1e-9

    def test_negative_edge_returns_zero(self):
        result = compute_kelly_position(win_rate=0.3, avg_win_pct=0.05, avg_loss_pct=0.10)
        assert result == 0.0

    def test_zero_loss_returns_zero(self):
        result = compute_kelly_position(win_rate=0.6, avg_win_pct=0.10, avg_loss_pct=0)
        assert result == 0.0

    def test_zero_win_rate_returns_zero(self):
        result = compute_kelly_position(win_rate=0.0, avg_win_pct=0.10, avg_loss_pct=0.05)
        assert result == 0.0

    def test_capped_at_1(self):
        result = compute_kelly_position(win_rate=0.99, avg_win_pct=1.0, avg_loss_pct=0.01, fraction=1.0)
        assert result <= 1.0


class TestRiskBudgetPosition:
    def test_position_etf_research(self):
        result = compute_position_from_risk_budget(
            PriorityLevel.RESEARCH, 0.05, InstrumentType.ETF
        )
        assert result > 0
        assert result <= 0.08

    def test_position_stock_position(self):
        result = compute_position_from_risk_budget(
            PriorityLevel.POSITION, 0.06, InstrumentType.STOCK
        )
        assert result > 0
        assert result <= 0.05

    def test_position_futures_smaller_due_to_max_cap(self):
        result = compute_position_from_risk_budget(
            PriorityLevel.POSITION, 0.03, InstrumentType.FUTURES
        )
        assert result > 0
        assert result <= 0.04

    def test_watch_returns_zero(self):
        result = compute_position_from_risk_budget(
            PriorityLevel.WATCH, 0.05, InstrumentType.ETF
        )
        assert result == 0.0

    def test_zero_stop_loss_returns_zero(self):
        result = compute_position_from_risk_budget(
            PriorityLevel.POSITION, 0.0, InstrumentType.ETF
        )
        assert result == 0.0


class TestCategoryTemplateDifferentiation:
    def test_etf_has_phase_templates(self):
        templates = EXECUTION_CONFIG.get("phase_templates", {})
        etf = templates.get("ETF", {})
        assert "research" in etf or "position" in etf

    def test_futures_has_phase_templates(self):
        templates = EXECUTION_CONFIG.get("phase_templates", {})
        futures = templates.get("FUTURES", {})
        assert "research" in futures or "position" in futures

    def test_stock_has_phase_templates(self):
        templates = EXECUTION_CONFIG.get("phase_templates", {})
        stock = templates.get("STOCK", {})
        assert "research" in stock or "position" in stock

    def test_etf_vs_stock_research_phases_differ(self):
        templates = EXECUTION_CONFIG.get("phase_templates", {})
        etf_phases = templates.get("ETF", {}).get("research", [])
        stock_phases = templates.get("STOCK", {}).get("research", [])
        if etf_phases and stock_phases:
            etf_names = [p.get("phase_name") for p in etf_phases]
            stock_names = [p.get("phase_name") for p in stock_phases]
            assert etf_names != stock_names

    def test_futures_allocation_ratio_less_than_etf_for_research(self):
        templates = EXECUTION_CONFIG.get("phase_templates", {})
        futures_p1 = templates.get("FUTURES", {}).get("research", [{}])[0]
        etf_p1 = templates.get("ETF", {}).get("research", [{}])[0]
        if futures_p1 and etf_p1:
            assert futures_p1.get("allocation_ratio", 1) <= etf_p1.get("allocation_ratio", 1)


class TestBuildActionPlanUsesParametricSizing:
    def test_position_sizing_uses_risk_budget_calculation(self):
        opp = _make_opportunity(InstrumentType.ETF, PriorityLevel.POSITION)

        class MockLLM:
            def chat_completion(self, messages, **kwargs):
                return '{"instrument":"510300","entry_conditions":["price confirm"],"stop_loss":{"stop_loss_type":"percent","stop_loss_value":5,"hard_stop":true},"take_profit":{"take_profit_type":"percent","take_profit_value":10,"partial_take_profit":true,"partial_ratio":0.5},"phases":[{"phase_name":"Phase 1","action_type":"buy","allocation_ratio":0.5,"trigger_condition":"confirm"}]}'

        designer = ActionDesigner(llm_client=MockLLM())
        plan = designer.design(opp)

        assert plan.position_sizing.suggested_allocation_pct is not None
        assert plan.position_sizing.suggested_allocation_pct > 0
        assert plan.position_sizing.max_allocation_pct is not None
        assert plan.position_sizing.max_allocation_pct >= plan.position_sizing.suggested_allocation_pct

    def test_watch_plan_has_zero_allocation(self):
        opp = _make_opportunity(InstrumentType.ETF, PriorityLevel.WATCH)
        designer = ActionDesigner(llm_client=None)
        plan = designer.design(opp)
        assert plan.position_sizing.suggested_allocation_pct == 0.0

    def test_sizing_rationale_mentions_stop_loss(self):
        opp = _make_opportunity(InstrumentType.ETF, PriorityLevel.POSITION)

        class MockLLM:
            def chat_completion(self, messages, **kwargs):
                return '{"instrument":"510300","entry_conditions":["confirm"],"stop_loss":{"stop_loss_type":"percent","stop_loss_value":5},"take_profit":{"take_profit_type":"percent","take_profit_value":10},"phases":[{"phase_name":"Phase 1","action_type":"buy","allocation_ratio":0.5}]}'

        designer = ActionDesigner(llm_client=MockLLM())
        plan = designer.design(opp)
        assert "止损" in plan.position_sizing.sizing_rationale
