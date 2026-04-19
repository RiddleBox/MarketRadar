import sys
from datetime import datetime, timedelta
sys.path.insert(0, r'D:\AIproject\MarketRadar')

from core.schemas import MarketSignal, SignalType, Market, Direction, TimeHorizon, SourceType, SignalLogicFrame
from m3_judgment.judgment_engine import JudgmentEngine

sig = MarketSignal(
    signal_type=SignalType.POLICY,
    signal_label='央行降准释放流动性',
    description='央行下调准备金率，提升市场流动性',
    evidence_text='下调存款准备金率0.5个百分点',
    affected_markets=[Market.A_SHARE],
    affected_instruments=['510300'],
    signal_direction=Direction.BULLISH,
    event_time=datetime.now(),
    time_horizon=TimeHorizon.SHORT,
    intensity_score=8,
    confidence_score=9,
    timeliness_score=9,
    source_type=SourceType.OFFICIAL_ANNOUNCEMENT,
    source_ref='test',
    logic_frame=SignalLogicFrame(
        what_changed='降准',
        change_direction=Direction.BULLISH,
        affects=['A股']
    )
)

raw = {
    'is_opportunity': True,
    'opportunity_title': '宽松政策驱动权益资产修复',
    'opportunity_thesis': '流动性改善有助于估值修复',
    'target_markets': ['A_SHARE'],
    'target_instruments': ['510300'],
    'trade_direction': 'LONG',
    'instrument_types': ['BONDS', 'STOCKS', 'ETF'],
    'opportunity_window': {
        'start': datetime.now().isoformat(),
        'end': (datetime.now() + timedelta(days=10)).isoformat(),
        'confidence_level': 0.72,
    },
    'why_now': '政策刚落地，市场预期重估开始',
    'supporting_evidence': ['政策超预期', '流动性释放'],
    'counter_evidence': ['经济修复仍需观察'],
    'key_assumptions': ['宽松继续传导'],
    'uncertainty_map': ['成交量不足'],
    'priority_level': 'POSITION',
    'risk_reward_profile': '3:1',
    'next_validation_questions': ['量价是否共振'],
}

engine = JudgmentEngine()
opp = engine._build_opportunity(raw, [sig], 'test_batch')
print('OK')
print('direction=', opp.trade_direction)
print('types=', opp.instrument_types)
print('priority=', opp.priority_level)
print('markets=', opp.target_markets)
