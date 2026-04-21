"""
tests/test_schemas.py — Schema 单元测试
"""
from __future__ import annotations

import pytest
from datetime import datetime
from core.schemas import (
    Market, InstrumentType, SignalType, Direction, TimeHorizon,
    PriorityLevel, PositionStatus, ActionType, SourceType,
    SignalLogicFrame, MarketSignal, OpportunityObject, TimeWindow,
    OpportunityScore, ActionPlan, StopLossConfig, TakeProfitConfig, ActionPhase,
    PositionSizing, Position, PositionUpdate,
)


class TestMarketSignal:
    def _make_signal(self, **kwargs):
        defaults = dict(
            signal_id="sig_001",
            signal_type=SignalType.MACRO,
            signal_label="测试信号",
            description="这是一条测试信号",
            evidence_text="原文证据",
            affected_markets=[Market.A_SHARE],
            affected_instruments=["沪深300"],
            signal_direction=Direction.BULLISH,
            event_time=datetime(2026, 1, 1, 9, 0),
            collected_time=datetime(2026, 1, 1, 10, 0),
            time_horizon=TimeHorizon.MEDIUM,
            intensity_score=7,
            confidence_score=8,
            timeliness_score=9,
            source_type=SourceType.NEWS,
            source_ref="test_ref_001",
            logic_frame=SignalLogicFrame(
                what_changed="央行利率下调",
                change_direction=Direction.BULLISH,
                affects=["债券", "股市"],
            ),
        )
        defaults.update(kwargs)
        return MarketSignal(**defaults)

    def test_create_basic(self):
        s = self._make_signal()
        assert s.signal_id == "sig_001"
        assert s.signal_type == SignalType.MACRO
        assert Market.A_SHARE in s.affected_markets
        assert s.intensity_score == 7

    def test_score_range_valid(self):
        s = self._make_signal(intensity_score=1, confidence_score=10, timeliness_score=5)
        assert s.intensity_score == 1
        assert s.confidence_score == 10

    def test_score_range_invalid_low(self):
        with pytest.raises(Exception):
            self._make_signal(intensity_score=0)

    def test_score_range_invalid_high(self):
        with pytest.raises(Exception):
            self._make_signal(confidence_score=11)

    def test_multiple_markets(self):
        s = self._make_signal(affected_markets=[Market.A_SHARE, Market.HK])
        assert len(s.affected_markets) == 2
        assert Market.HK in s.affected_markets

    def test_serialization(self):
        s = self._make_signal()
        data = s.model_dump(mode="json")
        assert data["signal_id"] == "sig_001"
        assert data["signal_type"] == "macro"
        assert data["affected_markets"] == ["A_SHARE"]

    def test_deserialization(self):
        s = self._make_signal()
        data = s.model_dump(mode="json")
        s2 = MarketSignal.model_validate(data)
        assert s2.signal_id == s.signal_id
        assert s2.signal_type == s.signal_type

    def test_optional_batch_id(self):
        s = self._make_signal()
        assert s.batch_id is None
        s2 = self._make_signal(batch_id="batch_001")
        assert s2.batch_id == "batch_001"


class TestOpportunityObject:
    def _make_opportunity(self, **kwargs):
        defaults = dict(
            opportunity_id="opp_001",
            opportunity_title="降息预期驱动A股反弹",
            opportunity_thesis="央行降息信号明确，叠加北向资金流入，A股大盘有望在接下来1-2个月内出现阶段性反弹机会。",
            target_markets=[Market.A_SHARE],
            target_instruments=["沪深300ETF", "上证50ETF"],
            trade_direction=Direction.BULLISH,
            instrument_types=[InstrumentType.ETF],
            opportunity_window=TimeWindow(
                start=datetime(2026, 4, 1),
                end=datetime(2026, 6, 30),
                confidence_level=0.7,
            ),
            why_now="本周央行发布降息信号，北向资金同步净流入，市场存在预期差",
            related_signals=["sig_001", "sig_002"],
            supporting_evidence=["央行降息预期升温", "北向资金净流入"],
            counter_evidence=["经济数据偏弱", "外部环境不确定"],
            key_assumptions=["降息政策在1个月内落地", "外部市场无重大风险事件"],
            uncertainty_map=["美联储政策变化（影响：高）", "国内经济数据超预期下行（影响：中）"],
            priority_level=PriorityLevel.RESEARCH,
            opportunity_score=OpportunityScore(
                catalyst_strength=8,
                timeliness=7,
                market_confirmation=7,
                tradability=8,
                risk_clarity=6,
                consensus_gap=7,
                signal_consistency=8,
                overall_score=7.29,
                confidence_score=0.78,
                execution_readiness=0.7,
            ),
            risk_reward_profile="潜在收益10-15%，止损5%，盈亏比约2-3:1",
            next_validation_questions=["降息具体幅度是多少？", "资金面持续性如何？"],
            judgment_version="v1.0",
            created_at=datetime(2026, 4, 13),
            batch_id="batch_001",
        )
        defaults.update(kwargs)
        return OpportunityObject(**defaults)

    def test_create_basic(self):
        opp = self._make_opportunity()
        assert opp.opportunity_id == "opp_001"
        assert opp.priority_level == PriorityLevel.RESEARCH
        assert Market.A_SHARE in opp.target_markets

    def test_optional_warnings(self):
        opp = self._make_opportunity()
        assert opp.warnings is None
        opp2 = self._make_opportunity(warnings=["证据来源均为新闻"])
        assert len(opp2.warnings) == 1

    def test_time_window(self):
        opp = self._make_opportunity()
        assert opp.opportunity_window.confidence_level == 0.7
        assert opp.opportunity_window.start < opp.opportunity_window.end

    def test_serialization_roundtrip(self):
        opp = self._make_opportunity()
        data = opp.model_dump(mode="json")
        opp2 = OpportunityObject.model_validate(data)
        assert opp2.opportunity_id == opp.opportunity_id
        assert opp2.priority_level == opp.priority_level
        assert len(opp2.related_signals) == 2


class TestActionPlan:
    def test_create_watch_plan(self):
        plan = ActionPlan(
            plan_id="plan_001",
            opportunity_id="opp_001",
            plan_summary="先观察政策兑现与量价配合，暂不直接入场。",
            primary_instruments=["沪深300ETF"],
            instrument_type=InstrumentType.ETF,
            direction=Direction.BULLISH,
            market=Market.A_SHARE,
            position_sizing=PositionSizing(
                suggested_allocation="0%",
                max_allocation="0%",
                sizing_rationale="watch 阶段不入场，仅跟踪验证。",
            ),
            stop_loss=StopLossConfig(stop_loss_type="percent", stop_loss_value=0.0, notes="观察阶段无实际止损执行"),
            take_profit=TakeProfitConfig(take_profit_type="percent", take_profit_value=0.0, notes="观察阶段无实际止盈执行"),
            phases=[
                ActionPhase(
                    phase_name="观察期",
                    action_type=ActionType.WATCH,
                    timing_description="持续观察政策细则与市场反馈。",
                    allocation_ratio=1.0,
                    trigger_condition="政策落地前",
                )
            ],
            valid_until=datetime(2026, 5, 13),
            review_triggers=["政策未落地", "量价背离扩大"],
            created_at=datetime(2026, 4, 13),
            opportunity_priority=PriorityLevel.WATCH,
        )
        assert plan.phases[0].action_type == ActionType.WATCH
        assert plan.position_sizing.suggested_allocation == "0%"

    def test_serialization(self):
        plan = ActionPlan(
            plan_id="plan_002",
            opportunity_id="opp_001",
            plan_summary="若降息兑现且指数放量突破，则分两阶段建立仓位。",
            primary_instruments=["沪深300ETF"],
            instrument_type=InstrumentType.ETF,
            direction=Direction.BULLISH,
            market=Market.A_SHARE,
            position_sizing=PositionSizing(
                suggested_allocation="3-5%",
                max_allocation="8%",
                sizing_rationale="宏观驱动较强，但仍需控制单主题风险暴露。",
            ),
            stop_loss=StopLossConfig(stop_loss_type="price", stop_loss_value=3.85, stop_loss_price=3.85, notes="跌破关键支撑离场"),
            take_profit=TakeProfitConfig(take_profit_type="price", take_profit_value=4.50, take_profit_price=4.50, notes="首目标位止盈"),
            phases=[
                ActionPhase(
                    phase_name="Phase 1",
                    action_type=ActionType.BUY,
                    timing_description="降息落地后首个放量日买入首批仓位。",
                    allocation_ratio=0.5,
                    trigger_condition="降息兑现",
                ),
            ],
            valid_until=datetime(2026, 4, 27),
            review_triggers=["收盘价跌破关键支撑", "政策预期逆转"],
            created_at=datetime(2026, 4, 13),
            opportunity_priority=PriorityLevel.RESEARCH,
        )
        data = plan.model_dump(mode="json")
        plan2 = ActionPlan.model_validate(data)
        assert plan2.stop_loss.stop_loss_price == 3.85
        assert plan2.take_profit.take_profit_price == 4.50


class TestEnums:
    def test_market_enum(self):
        assert Market.A_SHARE.value == "A_SHARE"
        assert Market("HK") == Market.HK

    def test_direction_enum(self):
        assert Direction.BULLISH.value == "BULLISH"
        assert Direction.BEARISH.value == "BEARISH"

    def test_priority_level_enum(self):
        assert PriorityLevel.WATCH.value == "watch"
        assert PriorityLevel.URGENT.value == "urgent"

    def test_signal_type_enum(self):
        types = [st.value for st in SignalType]
        assert "macro" in types
        assert "technical" in types
        assert "sentiment" in types  # 预留接口


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
