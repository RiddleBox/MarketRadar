from datetime import datetime, timedelta

from m4_action.action_designer import ActionDesigner
from core.schemas import (
    Direction,
    InstrumentType,
    Market,
    OpportunityObject,
    OpportunityScore,
    PriorityLevel,
    TimeWindow,
)


def _build_opportunity(title: str, thesis: str, why_now: str, supporting_evidence: list[str]) -> OpportunityObject:
    now = datetime(2026, 4, 14, 9, 30, 0)
    return OpportunityObject(
        opportunity_id="opp_test_m4_001",
        opportunity_title=title,
        opportunity_thesis=thesis,
        target_markets=[Market.A_SHARE],
        target_instruments=["510300"],
        trade_direction=Direction.BULLISH,
        instrument_types=[InstrumentType.ETF],
        opportunity_window=TimeWindow(
            start=now,
            end=now + timedelta(days=10),
            confidence_level=0.8,
        ),
        why_now=why_now,
        related_signals=["sig_test_001"],
        supporting_evidence=supporting_evidence,
        counter_evidence=[],
        key_assumptions=["流动性继续改善"],
        uncertainty_map=["情绪修复力度不足"],
        priority_level=PriorityLevel.POSITION,
        opportunity_score=OpportunityScore(
            catalyst_strength=8,
            timeliness=8,
            market_confirmation=7,
            tradability=8,
            risk_clarity=7,
            consensus_gap=7,
            signal_consistency=8,
            overall_score=7.8,
            confidence_score=0.78,
            execution_readiness=0.74,
        ),
        risk_reward_profile="收益弹性高于回撤风险",
        next_validation_questions=["量能是否持续放大"],
        invalidation_conditions=[],
        must_watch_indicators=[],
        kill_switch_signals=[],
        warnings=[],
        batch_id="batch_test",
    )


def test_resolve_default_strategy_macro_momentum():
    designer = ActionDesigner(llm_client=None)
    opp = _build_opportunity(
        title="央行宽松驱动权益修复",
        thesis="央行降准降息改善流动性环境",
        why_now="政策刚落地，窗口期短",
        supporting_evidence=["央行宣布降准 50bp", "货币环境转松"],
    )
    spec = designer.resolve_default_strategy_spec(opp)
    assert spec is not None
    assert spec.name == "MacroMomentum"


def test_resolve_default_strategy_policy_breakout():
    designer = ActionDesigner(llm_client=None)
    opp = _build_opportunity(
        title="产业政策催化主题机会",
        thesis="产业补贴和监管优化形成短线催化",
        why_now="政策发布后主题资金聚焦",
        supporting_evidence=["产业政策支持", "监管口径边际改善"],
    )
    spec = designer.resolve_default_strategy_spec(opp)
    assert spec is not None
    assert spec.name == "PolicyBreakout"


def test_resolve_default_strategy_combo_filter():
    designer = ActionDesigner(llm_client=None)
    opp = _build_opportunity(
        title="宽松与资金回流共振",
        thesis="央行宽松叠加北向资金流入，形成双确认",
        why_now="北向资金显著回流，量能同步放大",
        supporting_evidence=["央行降息", "北向资金连续净流入"],
    )
    spec = designer.resolve_default_strategy_spec(opp)
    assert spec is not None
    assert spec.name == "ComboFilter"
