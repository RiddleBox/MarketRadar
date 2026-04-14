from datetime import datetime

from m3_judgment.judgment_engine import JudgmentEngine
from core.schemas import Direction, Market, MarketSignal, SignalLogicFrame, SignalType, SourceType, TimeHorizon


def _build_signal() -> MarketSignal:
    now = datetime(2026, 4, 13, 10, 0, 0)
    return MarketSignal(
        signal_id="sig_test_001",
        signal_type=SignalType.MACRO,
        signal_label="央行宽松超预期",
        description="央行宣布降准降息，释放长期流动性并压低无风险利率。",
        evidence_text="人民银行宣布下调存款准备金率和逆回购利率。",
        affected_markets=[Market.A_SHARE],
        affected_instruments=["510300", "159915"],
        signal_direction=Direction.BULLISH,
        event_time=now,
        time_horizon=TimeHorizon.SHORT,
        intensity_score=9,
        confidence_score=9,
        timeliness_score=8,
        source_type=SourceType.OFFICIAL_ANNOUNCEMENT,
        source_ref="pbc.gov.cn/mock",
        logic_frame=SignalLogicFrame(
            what_changed="货币政策明显转松",
            change_direction=Direction.BULLISH,
            affects=["A股", "成长股", "券商股"],
        ),
        batch_id="batch_test",
    )


def test_parse_json_response_repairs_truncated_object_before_warnings():
    engine = JudgmentEngine(llm_client=None)
    raw = """```json
{
  \"is_opportunity\": true,
  \"opportunity_title\": \"央行超预期宽松组合拳\",
  \"opportunity_thesis\": \"流动性改善推动风险偏好修复\",
  \"target_markets\": [\"A_SHARE\"],
  \"target_instruments\": [\"券商ETF\", \"银行ETF\"],
  \"trade_direction\": \"BULLISH\",
  \"instrument_types\": [\"ETF\"],
  \"opportunity_window\": {
    \"start\": \"2026-04-14T09:30:00\",
    \"end\": \"2026-05-14T15:00:00\",
    \"confidence_level\": 0.82
  },
  \"why_now\": \"政策窗口刚开启\",
  \"supporting_evidence\": [\"政策力度超预期\"],
  \"counter_evidence\": [\"外部环境扰动\"],
  \"key_assumptions\": [\"流动性继续改善\"],
  \"uncertainty_map\": [\"传导存在时滞\"],
  \"priority_level\": \"position\",
  \"opportunity_score\": {
    \"catalyst_strength\": 9,
    \"timeliness\": 9,
    \"market_confirmation\": 7,
    \"tradability\": 8,
    \"risk_clarity\": 7,
    \"consensus_gap\": 8,
    \"signal_consistency\": 9,
    \"overall_score\": 8.1,
    \"confidence_score\": 0.82,
    \"execution_readiness\": 0.78
  },
  \"risk_reward_profile\": \"短期收益空间可观\",
  \"next_validation_questions\": [\"量能是否放大\"],
  \"invalidation_conditions\": [\"三日内跌破关键位\"],
  \"must_watch_indicators\": [\"DR007\"],
  \"kill_switch_signals\": [\"央行口径转鹰\"],
  \"warnings\": [
    \"注意：信号来源未标注官方公告\"
"""
    data = engine._parse_json_response(raw, expected_key=None)
    assert data["is_opportunity"] is True
    assert data["opportunity_title"] == "央行超预期宽松组合拳"
    assert data["priority_level"] == "position"
    assert "opportunity_score" in data
    assert data["opportunity_score"]["execution_readiness"] == 0.78


def test_repaired_partial_json_is_still_buildable_to_opportunity():
    engine = JudgmentEngine(llm_client=None)
    raw = """```json
{
  \"is_opportunity\": true,
  \"opportunity_title\": \"央行超预期宽松组合拳\",
  \"opportunity_thesis\": \"流动性改善推动风险偏好修复\",
  \"target_markets\": [\"A_SHARE\"],
  \"target_instruments\": [\"券商ETF\", \"银行ETF\"],
  \"trade_direction\": \"BULLISH\",
  \"instrument_types\": [\"ETF\"],
  \"opportunity_window\": {
    \"start\": \"2026-04-14T09:30:00\",
    \"end\": \"2026-05-14T15:00:00\",
    \"confidence_level\": 0.82
  },
  \"why_now\": \"政策窗口刚开启\",
  \"supporting_evidence\": [\"政策力度超预期\"],
  \"counter_evidence\": [\"外部环境扰动\"],
  \"key_assumptions\": [\"流动性继续改善\"],
  \"uncertainty_map\": [\"传导存在时滞\"],
  \"priority_level\": \"position\",
  \"opportunity_score\": {
    \"catalyst_strength\": 9,
    \"timeliness\": 9,
    \"market_confirmation\": 7,
    \"tradability\": 8,
    \"risk_clarity\": 7,
    \"consensus_gap\": 8,
    \"signal_consistency\": 9,
    \"overall_score\": 8.1,
    \"confidence_score\": 0.82,
    \"execution_readiness\": 0.78
  },
  \"warnings\": [
    \"注意：信号来源未标注官方公告\"
"""
    data = engine._parse_json_response(raw, expected_key=None)
    opp = engine._build_opportunity(data, [_build_signal()], "batch_test")
    assert opp.opportunity_title == "央行超预期宽松组合拳"
    assert opp.priority_level.value == "position"
