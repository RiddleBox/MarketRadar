from datetime import datetime, timedelta

from core.schemas import (
    Direction,
    Market,
    MarketSignal,
    SignalLogicFrame,
    SignalType,
    SourceType,
    TimeHorizon,
)
from m3_judgment.judgment_engine import JudgmentEngine


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


def test_build_opportunity_normalizes_common_llm_aliases():
    engine = JudgmentEngine(llm_client=None)
    signal = _build_signal()
    start = datetime(2026, 4, 14, 9, 30, 0)
    end = start + timedelta(days=10)

    data = {
        "opportunity_title": "宽松政策驱动权益修复",
        "opportunity_thesis": "流动性改善推动风险偏好回升。",
        "target_markets": ["A", "HK"],
        "target_instruments": ["510300", "恒生科技ETF"],
        "trade_direction": "LONG",
        "instrument_types": ["BONDS", "ETFS", "INDEX_FUTURES"],
        "opportunity_window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "confidence_level": 0.72,
        },
        "priority_level": "POSITION",
        "why_now": "政策刚落地，市场尚未完全定价。",
        "risk_reward_profile": "向上弹性大于下行回撤",
    }

    opp = engine._build_opportunity(data, [signal], "batch_test")

    assert opp.target_markets == [Market.A_SHARE, Market.HK]
    assert opp.trade_direction == Direction.BULLISH
    assert [item.value for item in opp.instrument_types] == ["BOND", "ETF", "FUTURES"]
    assert opp.priority_level.value == "position"
    assert opp.opportunity_window.start == start
    assert opp.opportunity_window.end == end


def test_build_opportunity_uses_safe_defaults_when_window_invalid():
    engine = JudgmentEngine(llm_client=None)
    signal = _build_signal()
    start = datetime(2026, 4, 14, 9, 30, 0)

    data = {
        "opportunity_title": "时间窗回退测试",
        "target_markets": ["CHINA"],
        "trade_direction": "BUY",
        "instrument_types": ["EQUITY"],
        "opportunity_window": {
            "start": start.isoformat(),
            "end": start.isoformat(),
        },
    }

    opp = engine._build_opportunity(data, [signal], "batch_test")

    assert opp.target_markets == [Market.A_SHARE]
    assert opp.trade_direction == Direction.BULLISH
    assert [item.value for item in opp.instrument_types] == ["STOCK"]
    assert opp.opportunity_window.end > opp.opportunity_window.start


def test_build_opportunity_ignores_unknown_market_and_instrument_values():
    engine = JudgmentEngine(llm_client=None)
    signal = _build_signal()
    start = datetime(2026, 4, 14, 9, 30, 0)
    end = start + timedelta(days=5)

    data = {
        "opportunity_title": "未知枚举容错测试",
        "target_markets": ["A", "BONDS_MARKET", "HK"],
        "trade_direction": "LONG",
        "instrument_types": ["ETFS", "SWAP", "BONDS"],
        "opportunity_window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "confidence_level": 0.8,
        },
    }

    opp = engine._build_opportunity(data, [signal], "batch_test")

    assert opp.target_markets == [Market.A_SHARE, Market.HK]
    assert [item.value for item in opp.instrument_types] == ["ETF", "BOND"]


def test_parse_json_response_supports_markdown_code_fence():
    engine = JudgmentEngine(llm_client=None)
    raw = """```json
{\n  \"is_opportunity\": true,\n  \"opportunity_title\": \"测试\"\n}
```"""
    data = engine._parse_json_response(raw)
    assert data["is_opportunity"] is True
    assert data["opportunity_title"] == "测试"
