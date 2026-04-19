"""
tests/test_m3_calibration.py — M3 评分校准与失效条件验证测试
"""
from core.schemas import OpportunityScore, PriorityLevel
from m3_judgment.judgment_engine import JudgmentEngine


def _score(
    overall: float = 5.0,
    confidence: float = 0.5,
    timeliness: int = 5,
    execution_readiness: float = 0.5,
    **kw,
) -> OpportunityScore:
    defaults = dict(
        catalyst_strength=5, timeliness=timeliness, market_confirmation=5,
        tradability=5, risk_clarity=5, consensus_gap=5, signal_consistency=5,
        overall_score=overall, confidence_score=confidence,
        execution_readiness=execution_readiness,
    )
    defaults.update(kw)
    return OpportunityScore(**defaults)


class TestCalibratePriority:
    def test_high_score_with_high_confidence_upgrades_to_position(self):
        s = _score(overall=8.5, confidence=0.85, timeliness=7)
        result = JudgmentEngine._calibrate_priority("research", s)
        assert result == PriorityLevel.POSITION.value

    def test_high_score_with_very_high_timeliness_upgrades_to_urgent(self):
        s = _score(overall=8.2, confidence=0.85, timeliness=9)
        result = JudgmentEngine._calibrate_priority("research", s)
        assert result == PriorityLevel.URGENT.value

    def test_medium_score_with_good_execution_becomes_research(self):
        s = _score(overall=6.5, execution_readiness=0.7)
        result = JudgmentEngine._calibrate_priority("watch", s)
        assert result == PriorityLevel.RESEARCH.value

    def test_medium_score_with_position_stays_position(self):
        s = _score(overall=6.5, execution_readiness=0.7)
        result = JudgmentEngine._calibrate_priority("position", s)
        assert result == PriorityLevel.POSITION.value

    def test_low_score_forces_watch(self):
        s = _score(overall=3.5, confidence=0.9)
        result = JudgmentEngine._calibrate_priority("position", s)
        assert result == PriorityLevel.WATCH.value

    def test_medium_score_low_execution_keeps_llm_priority(self):
        s = _score(overall=5.0, execution_readiness=0.3)
        result = JudgmentEngine._calibrate_priority("research", s)
        assert result == PriorityLevel.RESEARCH.value

    def test_invalid_llm_priority_falls_back_to_watch(self):
        s = _score(overall=5.0)
        result = JudgmentEngine._calibrate_priority("invalid_level", s)
        assert result == PriorityLevel.WATCH.value

    def test_high_score_insufficient_confidence_keeps_llm(self):
        s = _score(overall=8.0, confidence=0.7, timeliness=5)
        result = JudgmentEngine._calibrate_priority("research", s)
        assert result == PriorityLevel.RESEARCH.value

    def test_boundary_overall_8_confidence_08(self):
        s = _score(overall=8.0, confidence=0.8, timeliness=7)
        result = JudgmentEngine._calibrate_priority("research", s)
        assert result == PriorityLevel.POSITION.value


class TestValidateInvalidationConditions:
    def test_empty_invalidation_gets_default(self):
        inv, ks = JudgmentEngine._validate_invalidation_conditions(
            [], ["price drops 5%"], "test"
        )
        assert len(inv) >= 1
        assert inv[0] == "核心假设被证伪"

    def test_empty_kill_switch_gets_default(self):
        inv, ks = JudgmentEngine._validate_invalidation_conditions(
            ["假设1被证伪"], [], "test"
        )
        assert len(ks) >= 1

    def test_overlap_deduplicated(self):
        inv = ["核心假设被证伪", "政策转向"]
        ks = ["核心假设被证伪", "市场崩盘"]
        inv_out, ks_out = JudgmentEngine._validate_invalidation_conditions(inv, ks, "test")
        overlap_count = len(set(inv_out) & set(ks_out))
        assert overlap_count <= 1

    def test_vague_condition_triggers_warning(self):
        inv, ks = JudgmentEngine._validate_invalidation_conditions(
            ["跌", "政策完全转向"], ["崩"], "test"
        )
        assert len(inv) == 2
        assert len(ks) >= 1

    def test_normal_conditions_pass_through(self):
        inv = ["央行重新收紧货币政策", "北向资金连续5日净流出超50亿"]
        ks = ["沪深300跌破250日均线", "信用利差急剧走阔"]
        inv_out, ks_out = JudgmentEngine._validate_invalidation_conditions(inv, ks, "test")
        assert inv_out == inv
        assert ks_out == ks
