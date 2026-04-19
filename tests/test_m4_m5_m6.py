"""
tests/test_m4_m5_m6.py — M4→M5→M6 闭环联调测试

覆盖：
  1. ActionPlan 包含 direction/market 字段
  2. position_bridge: ActionPlan → Position
  3. M5 止损/止盈检查
  4. M6 复盘归因（mock LLM）
"""
import json
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from core.schemas import (
    ActionPlan, ActionPhase, ActionType, Direction, InstrumentType,
    Market, OpportunityObject, OpportunityScore, Position, PositionStatus,
    PriorityLevel, StopLossConfig, TakeProfitConfig, PositionSizing, TimeWindow,
)
from pipeline.position_bridge import open_positions_from_plan


def _make_opportunity() -> OpportunityObject:
    return OpportunityObject(
        opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
        opportunity_title="降息驱动A股反弹",
        opportunity_thesis="央行超预期降息25bp，北向资金大幅流入",
        priority_level=PriorityLevel.POSITION,
        trade_direction=Direction.BULLISH,
        target_markets=[Market.A_SHARE],
        target_instruments=["510300.SH", "510050.SH"],
        instrument_types=[InstrumentType.ETF],
        opportunity_window=TimeWindow(
            start=datetime.now(),
            end=datetime.now() + timedelta(days=7),
            confidence_level=0.7,
        ),
        why_now="催化剂集中爆发",
        related_signals=["sig_001", "sig_002"],
        supporting_evidence=["央行超预期降息25bp"],
        counter_evidence=["外部地缘风险"],
        key_assumptions=["政策传导有效"],
        uncertainty_map=["地缘风险"],
        risk_reward_profile="盈亏比 2:1",
        next_validation_questions=["专项债发行节奏？"],
        opportunity_score=OpportunityScore(
            catalyst_strength=8, timeliness=9, market_confirmation=7,
            tradability=8, risk_clarity=6, consensus_gap=7,
            signal_consistency=8, overall_score=7.5, confidence_score=0.8,
            execution_readiness=0.7,
        ),
        batch_id="test_bridge",
    )


def _make_plan(opp: OpportunityObject) -> ActionPlan:
    return ActionPlan(
        opportunity_id=opp.opportunity_id,
        plan_summary="BULLISH | 510300.SH, 510050.SH",
        primary_instruments=["510300.SH", "510050.SH"],
        instrument_type=InstrumentType.ETF,
        direction=opp.trade_direction,
        market=opp.target_markets[0],
        stop_loss=StopLossConfig(
            stop_loss_type="percent",
            stop_loss_value=5.0,
            hard_stop=True,
        ),
        take_profit=TakeProfitConfig(
            take_profit_type="percent",
            take_profit_value=10.0,
        ),
        position_sizing=PositionSizing(
            suggested_allocation="5-8%",
            max_allocation="不超过10%",
            sizing_rationale="position级机会",
            suggested_allocation_pct=0.05,
            max_allocation_pct=0.10,
        ),
        phases=[
            ActionPhase(
                phase_name="第一批建仓",
                action_type=ActionType.BUY,
                timing_description="入场信号满足时",
                allocation_ratio=0.5,
                trigger_condition="价格回调确认",
            ),
        ],
        valid_until=datetime.now() + timedelta(days=7),
        review_triggers=["7天内未触发入场则重新评估"],
        opportunity_priority=PriorityLevel.POSITION,
    )


class TestActionPlanFields:
    def test_direction_field(self):
        opp = _make_opportunity()
        plan = _make_plan(opp)
        assert plan.direction == Direction.BULLISH

    def test_market_field(self):
        opp = _make_opportunity()
        plan = _make_plan(opp)
        assert plan.market == Market.A_SHARE

    def test_position_sizing_numeric(self):
        plan = _make_plan(_make_opportunity())
        assert plan.position_sizing.suggested_allocation_pct == 0.05
        assert plan.position_sizing.max_allocation_pct == 0.10


class TestPositionBridge:
    def test_open_positions_from_plan(self):
        plan = _make_plan(_make_opportunity())
        positions = open_positions_from_plan(
            plan=plan,
            entry_price=3.80,
            total_capital=1_000_000,
        )
        assert len(positions) == 2
        for pos in positions:
            assert pos.status == PositionStatus.OPEN
            assert pos.stop_loss_price > 0
            assert pos.take_profit_price > 0
            assert pos.entry_price == 3.80

    def test_stop_loss_price_derived(self):
        plan = _make_plan(_make_opportunity())
        positions = open_positions_from_plan(plan=plan, entry_price=3.80)
        expected_sl = 3.80 * (1 - 5.0 / 100)
        assert abs(positions[0].stop_loss_price - expected_sl) < 0.01

    def test_take_profit_price_derived(self):
        plan = _make_plan(_make_opportunity())
        positions = open_positions_from_plan(plan=plan, entry_price=3.80)
        expected_tp = 3.80 * (1 + 10.0 / 100)
        assert abs(positions[0].take_profit_price - expected_tp) < 0.01


class TestM5M6Retro:
    def test_closed_position_retrospective(self):
        opp = _make_opportunity()
        plan = _make_plan(opp)
        positions = open_positions_from_plan(plan=plan, entry_price=3.80)

        pos = positions[0]

        class MockLLM:
            def chat_completion(self, messages, **kwargs):
                return json.dumps({
                    "signal_quality_score": 4,
                    "signal_quality_comment": "信号准确",
                    "judgment_quality_score": 3,
                    "judgment_quality_comment": "论点成立",
                    "timing_quality_score": 4,
                    "timing_quality_comment": "时机合理",
                    "luck_vs_skill": "判断力驱动",
                    "assumption_verification": "假设1部分验证",
                    "key_lesson": "宏观+资金流共振胜率高",
                    "system_improvement": "增加时间止损字段",
                })

        import m6_retrospective.retrospective as retro_mod
        tmpdir = Path(tempfile.mkdtemp())
        orig = retro_mod.RETRO_DIR
        retro_mod.RETRO_DIR = tmpdir / "retrospectives"
        retro_mod.RETRO_DIR.mkdir(parents=True, exist_ok=True)

        try:
            from m6_retrospective.retrospective import RetrospectiveEngine
            engine = RetrospectiveEngine(llm_client=MockLLM())

            closed_pos = pos.model_copy(update={
                "status": PositionStatus.TAKE_PROFIT,
                "exit_price": 4.18,
                "exit_time": datetime.now(),
                "exit_reason": "止盈触发",
                "realized_pnl": 0.10,
                "realized_pnl_pct": 0.10,
            })

            report = engine.analyze(
                opportunity=opp,
                position=closed_pos,
                outcome="TAKE_PROFIT",
                notes="按计划止盈",
            )
            assert report["outcome"] == "TAKE_PROFIT"
            assert report["composite_score"] > 0
        finally:
            retro_mod.RETRO_DIR = orig
