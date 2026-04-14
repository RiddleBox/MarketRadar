from datetime import datetime, timedelta
from pathlib import Path
import json
import tempfile

from core.schemas import (
    Direction,
    Market,
    OpportunityObject,
    OpportunityScore,
    PriorityLevel,
    TimeWindow,
)
from m3_judgment.sentiment_resonance import SentimentResonanceEnhancer, SentimentContext


def _build_opp(direction=Direction.BULLISH, priority=PriorityLevel.WATCH, execution_readiness=0.45):
    now = datetime(2026, 4, 14, 10, 0, 0)
    return OpportunityObject(
        opportunity_id="opp_test",
        opportunity_title="测试机会",
        opportunity_thesis="测试 thesis",
        target_markets=[Market.A_SHARE],
        target_instruments=["510300"],
        trade_direction=direction,
        instrument_types=["ETF"],
        opportunity_window=TimeWindow(start=now, end=now + timedelta(days=5), confidence_level=0.7),
        why_now="测试",
        related_signals=["sig_1"],
        supporting_evidence=["e1"],
        counter_evidence=[],
        key_assumptions=["a1"],
        uncertainty_map=["u1"],
        priority_level=priority,
        opportunity_score=OpportunityScore(
            catalyst_strength=7,
            timeliness=7,
            market_confirmation=6,
            tradability=7,
            risk_clarity=6,
            consensus_gap=6,
            signal_consistency=7,
            overall_score=6.57,
            confidence_score=0.72,
            execution_readiness=execution_readiness,
        ),
        risk_reward_profile="ok",
        next_validation_questions=["q1"],
        invalidation_conditions=["i1"],
        must_watch_indicators=["m1"],
        kill_switch_signals=["k1"],
        warnings=[],
        judgment_version="v1.0",
        created_at=now,
        batch_id="batch_test",
    )


def test_resonance_boosts_aligned_bullish_opportunity():
    enhancer = SentimentResonanceEnhancer()
    opp = _build_opp(direction=Direction.BULLISH, priority=PriorityLevel.WATCH, execution_readiness=0.45)
    ctx = SentimentContext(fear_greed_score=68.0, sentiment_label="偏多", direction="BULLISH")

    out = enhancer.enhance(opp, ctx)

    assert out.priority_level == PriorityLevel.POSITION
    assert out.opportunity_score.execution_readiness > opp.opportunity_score.execution_readiness
    assert any("情绪共振增强" in w for w in (out.warnings or []))


def test_resonance_flags_opposed_direction():
    enhancer = SentimentResonanceEnhancer()
    opp = _build_opp(direction=Direction.BEARISH, priority=PriorityLevel.POSITION, execution_readiness=0.6)
    ctx = SentimentContext(fear_greed_score=62.0, sentiment_label="偏多", direction="BULLISH")

    out = enhancer.enhance(opp, ctx)

    assert out.opportunity_score.execution_readiness < opp.opportunity_score.execution_readiness
    assert any("情绪背离" in w for w in (out.warnings or []))


def test_load_latest_context_from_snapshot_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "latest.json"
        p.write_text(json.dumps({
            "fear_greed_score": 22.5,
            "sentiment_label": "极度恐惧",
            "direction": "BEARISH",
            "trend_is_rising": False,
        }, ensure_ascii=False), encoding="utf-8")

        enhancer = SentimentResonanceEnhancer(snapshot_path=p)
        ctx = enhancer.load_latest_context()

        assert ctx is not None
        assert ctx.is_extreme_fear is True
        assert ctx.direction == "BEARISH"
