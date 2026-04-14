import json
from pathlib import Path

from backtest.strategy_backtest import StrategyBacktester


def test_load_events_from_opportunities_supports_m3_style_payload(tmp_path: Path):
    payload = {
        "opportunity_id": "opp_test_001",
        "opportunity_title": "宽松与资金回流共振",
        "opportunity_thesis": "央行降息叠加北向资金净流入，风险偏好修复。",
        "target_markets": ["A_SHARE"],
        "target_instruments": ["510300.SH"],
        "trade_direction": "BULLISH",
        "opportunity_window": {
            "start": "2026-04-14T09:30:00",
            "end": "2026-05-14T15:00:00",
            "confidence_level": 0.82,
        },
        "why_now": "政策落地且资金回流同步出现。",
        "supporting_evidence": ["央行降息", "北向资金净流入 160 亿"],
        "created_at": "2026-04-14T10:00:00",
        "opportunity_score": {
            "catalyst_strength": 9,
            "confidence_score": 0.82,
            "overall_score": 8.1,
        },
    }
    p = tmp_path / "opp.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    bt = StrategyBacktester(use_seed=False)
    events = bt.load_events_from_opportunities(tmp_path)

    assert len(events) == 1
    event = events[0]
    assert event.instrument == "510300.SH"
    assert event.market == "A_SHARE"
    assert event.signal_direction == "BULLISH"
    assert event.signal_type == "capital_flow"
    assert event.signal_intensity == 9
    assert event.signal_confidence == 8.2
    assert event.time_horizon == "medium"


def test_load_events_from_opportunities_normalizes_common_instrument_aliases(tmp_path: Path):
    payload = {
        "opportunity_id": "opp_test_002",
        "opportunity_title": "半导体政策催化",
        "target_markets": ["A_SHARE"],
        "target_instruments": ["半导体ETF（512480）"],
        "trade_direction": "BULLISH",
        "opportunity_window": {
            "start": "2026-04-14T09:30:00",
            "end": "2026-04-20T15:00:00",
            "confidence_level": 0.75,
        },
        "why_now": "政策催化落地。",
        "supporting_evidence": ["产业政策支持"],
        "created_at": "2026-04-14T10:00:00",
        "opportunity_score": {
            "catalyst_strength": 8,
            "confidence_score": 0.76,
        },
    }
    p = tmp_path / "opp2.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    bt = StrategyBacktester(use_seed=False)
    events = bt.load_events_from_opportunities(tmp_path)

    assert len(events) == 1
    assert events[0].instrument == "512480.SH"
