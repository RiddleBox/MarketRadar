"""
tests/test_m6.py — M6 复盘归因引擎测试

覆盖：
  1. 单次复盘（mock LLM，验证结构和持久化）
  2. 批量复盘扫描
  3. 汇总统计
  4. Outcome 自动推断
"""
import os, json, tempfile, uuid
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from m6_retrospective.retrospective import RetrospectiveEngine
from core.schemas import (
    OpportunityObject, OpportunityScore, Position, PositionStatus, PriorityLevel,
    Direction, Market, InstrumentType, TimeWindow,
)


def _make_opportunity(title="降息驱动A股反弹", priority="research") -> OpportunityObject:
    now = datetime.now()
    return OpportunityObject(
        opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
        opportunity_title=title,
        opportunity_thesis="央行超预期降息25bp，北向资金大幅流入，市场短期情绪改善，构成短线反弹机会。",
        priority_level=PriorityLevel(priority.lower()),
        trade_direction=Direction.BULLISH,
        target_markets=[Market.A_SHARE],
        target_instruments=["沪深300ETF", "上证50ETF"],
        instrument_types=[InstrumentType.ETF],
        opportunity_window=TimeWindow(
            start=datetime.now(),
            end=datetime.now() + timedelta(days=7),
            confidence_level=0.7,
        ),
        why_now="催化剂集中爆发（降息+资金流入+技术突破），市场已即时反应。",
        related_signals=["sig_001", "sig_002", "sig_003"],
        supporting_evidence=["央行超预期降息25bp", "北向资金净流入168亿", "沪深300放量突破"],
        counter_evidence=["外部地缘风险尚存", "经济基本面未见实质改善"],
        key_assumptions=["假设1：政策传导有效，后续专项债按期发行", "假设2：资金流入持续，非一日游"],
        uncertainty_map=["地缘风险发酵可能打断行情"],
        risk_reward_profile="预期盈亏比 2:1，止损-5%，目标+10%",
        next_validation_questions=["专项债发行节奏？", "外资持续流入还是一次性？"],
        opportunity_score=OpportunityScore(
            catalyst_strength=8, timeliness=9, market_confirmation=7,
            tradability=8, risk_clarity=6, consensus_gap=7,
            signal_consistency=8, overall_score=7.5, confidence_score=0.8,
            execution_readiness=0.7,
        ),
        batch_id="test_batch",
    )


def _make_closed_position(
    instrument="510300.SH",
    entry=3.80,
    exit_price=4.18,
    pnl=0.10,
    exit_reason="止盈触发",
) -> Position:
    now = datetime.now()
    opp_id = f"opp_{uuid.uuid4().hex[:8]}"
    plan_id = f"plan_{uuid.uuid4().hex[:8]}"
    return Position(
        plan_id=plan_id,
        opportunity_id=opp_id,
        instrument=instrument,
        instrument_type=InstrumentType.ETF,
        market=Market.A_SHARE,
        direction=Direction.BULLISH,
        quantity=10000.0,
        entry_price=entry,
        current_price=exit_price,
        exit_price=exit_price,
        stop_loss_price=entry * 0.95,
        take_profit_price=entry * 1.10,
        total_cost=entry * 10000,
        unrealized_pnl=pnl,
        realized_pnl=pnl,
        status=PositionStatus.CLOSED,
        entry_time=now - timedelta(days=3),
        exit_time=now,
        exit_reason=exit_reason,
        updates=[],
    )


class MockLLM:
    def chat_completion(self, messages, **kwargs):
        return json.dumps({
            "signal_quality_score": 4,
            "signal_quality_comment": "信号提取准确",
            "judgment_quality_score": 3,
            "judgment_quality_comment": "论点成立但时机判断略早",
            "timing_quality_score": 4,
            "timing_quality_comment": "入场时机合理",
            "luck_vs_skill": "主要来自判断力",
            "assumption_verification": "假设1尚未验证",
            "key_lesson": "宏观政策信号+资金流共振时短线反弹胜率高",
            "system_improvement": "M3 应新增时间止损字段",
        })


class TestRetrospectiveEngine:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        import m6_retrospective.retrospective as retro_mod
        self._orig_retro_dir = retro_mod.RETRO_DIR
        retro_mod.RETRO_DIR = self.tmpdir / "retrospectives"
        retro_mod.RETRO_DIR.mkdir(parents=True, exist_ok=True)
        self.engine = RetrospectiveEngine(llm_client=MockLLM())

    def teardown_method(self):
        import m6_retrospective.retrospective as retro_mod
        retro_mod.RETRO_DIR = self._orig_retro_dir

    def test_single_retro_structure_and_persistence(self):
        opp = _make_opportunity()
        pos = _make_closed_position()
        pos.opportunity_id = opp.opportunity_id

        report = self.engine.analyze(opp, pos, outcome="TAKE_PROFIT", notes="按计划止盈")

        assert report["retro_id"].startswith("retro_")
        assert report["outcome"] == "TAKE_PROFIT"
        assert report["composite_score"] > 0
        import m6_retrospective.retrospective as retro_mod
        assert (retro_mod.RETRO_DIR / f"{report['retro_id']}.json").exists()

    def test_batch_analyze(self):
        positions = [
            _make_closed_position("510300.SH", 3.80, 4.18, 0.10, "止盈触发"),
            _make_closed_position("512480.SH", 5.20, 4.94, -0.05, "止损触发"),
            _make_closed_position("159755.SZ", 1.80, 1.96, 0.089, "手动平仓"),
        ]
        reports = self.engine.batch_analyze_closed_positions(
            positions=positions, opportunities_map={}
        )
        assert len(reports) == 3

        reports2 = self.engine.batch_analyze_closed_positions(positions=positions)
        assert len(reports2) == 0

    def test_summarize(self):
        positions = [_make_closed_position(exit_reason="止盈触发")]
        self.engine.batch_analyze_closed_positions(positions=positions, opportunities_map={})
        summary = self.engine.summarize()
        assert summary["total"] >= 1

    def test_infer_outcome(self):
        cases = [
            (_make_closed_position(exit_reason="止盈触发"), "TAKE_PROFIT"),
            (_make_closed_position(exit_reason="stop_loss triggered"), "STOP_LOSS"),
            (_make_closed_position(pnl=0.08, exit_reason="手动"), "HIT"),
            (_make_closed_position(pnl=-0.03, exit_reason="手动"), "MISS"),
        ]
        for pos, expected in cases:
            actual = self.engine._infer_outcome(pos)
            assert actual == expected, f"推断错误: 期望{expected}，实际{actual}"
