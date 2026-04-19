"""
tests/test_m11.py — M11 MultiAgentSim 测试

覆盖：
  1. Schema 验证
  2. 各 Agent 规则分析（离线）
  3. AgentNetwork 序列传导端到端
  4. HistoricalCalibrator 校准
  5. EventCatalog 事件生成
  6. CalibrationStore 持久化
  7. ValidationCase / CalibrationRun schema
"""
from datetime import datetime
from pathlib import Path
import tempfile

from m11_agent_sim.schemas import (
    AgentConfig, AgentOutput, MarketInput, NetworkConfig,
    SentimentDistribution, PriceContext, SentimentContext, SignalContext,
    ValidationCase, CalibrationRun, CalibrationScore,
)
from m11_agent_sim.agents import (
    PolicySensitiveAgent, NorthboundFollowerAgent,
    TechnicalAgent, SentimentRetailAgent, FundamentalAgent,
)
from m11_agent_sim.agent_network import AgentNetwork
from m11_agent_sim.calibrator import HistoricalCalibrator


def _make_bullish_input():
    return MarketInput(
        timestamp=datetime(2024, 9, 24),
        market="A_SHARE",
        event_description="央行宣布降准50bp+降息，历史性宽松",
        sentiment=SentimentContext(
            fear_greed_index=35.0,
            sentiment_label="恐惧",
            northbound_flow=120.0,
            advance_decline_ratio=0.72,
            weibo_sentiment=0.2,
        ),
        signals=SignalContext(
            bullish_count=3, bearish_count=0, neutral_count=0,
            dominant_signal_type="policy_document",
            avg_intensity=9.5, avg_confidence=9.0,
        ),
        price=PriceContext(
            current_price=3.382, price_5d_chg_pct=-0.02,
            price_20d_chg_pct=-0.08, ma5=3.40, ma20=3.55,
            above_ma5=False, above_ma20=False, volume_ratio=2.5,
        ),
    )


def _make_bearish_input():
    return MarketInput(
        timestamp=datetime(2025, 4, 7),
        market="A_SHARE",
        event_description="美国对华加征关税145%",
        sentiment=SentimentContext(
            fear_greed_index=22.0,
            sentiment_label="恐惧",
            northbound_flow=-95.0,
            advance_decline_ratio=0.28,
            weibo_sentiment=-0.5,
        ),
        signals=SignalContext(
            bullish_count=0, bearish_count=3, neutral_count=0,
            dominant_signal_type="market_data",
            avg_intensity=8.5, avg_confidence=8.0,
        ),
        price=PriceContext(
            current_price=3.748, price_5d_chg_pct=-0.05,
            price_20d_chg_pct=-0.12, ma5=3.90, ma20=4.10,
            above_ma5=False, above_ma20=False, volume_ratio=1.8,
        ),
    )


class TestSchema:
    def test_market_input(self):
        mi = _make_bullish_input()
        assert mi.market == "A_SHARE"
        assert mi.sentiment.fear_greed_index == 35.0

    def test_agent_output_normalize(self):
        out = AgentOutput(
            agent_type="test",
            bullish_prob=0.6, bearish_prob=0.3, neutral_prob=0.2,
        )
        out = out.normalize_probs()
        assert abs(out.bullish_prob + out.bearish_prob + out.neutral_prob - 1.0) < 0.001

    def test_sentiment_distribution_summary(self):
        dist = SentimentDistribution(
            direction="BULLISH",
            bullish_prob=0.65, bearish_prob=0.20, neutral_prob=0.15,
            intensity=7.5, confidence=0.75,
        )
        summary = dist.summary()
        assert "BULLISH" in summary


class TestAgents:
    def test_policy_agent_bullish(self):
        pa = PolicySensitiveAgent(use_llm=False)
        out = pa.analyze(_make_bullish_input())
        assert out.bullish_prob > out.bearish_prob

    def test_policy_agent_bearish(self):
        pa = PolicySensitiveAgent(use_llm=False)
        out = pa.analyze(_make_bearish_input())
        assert out.bearish_prob > out.bullish_prob

    def test_northbound_agent_bullish(self):
        na = NorthboundFollowerAgent(use_llm=False)
        out = na.analyze(_make_bullish_input())
        assert out.bullish_prob > 0.5

    def test_northbound_agent_bearish(self):
        na = NorthboundFollowerAgent(use_llm=False)
        out = na.analyze(_make_bearish_input())
        assert out.bearish_prob > 0.5


class TestAgentNetwork:
    def test_sequential_bullish(self):
        net = AgentNetwork._default_a_share(topology="sequential", use_llm=False)
        dist = net.run(_make_bullish_input())
        assert dist.direction == "BULLISH"
        assert dist.bullish_prob > 0.5
        assert len(dist.agent_outputs) == 5

    def test_sequential_bearish(self):
        net = AgentNetwork._default_a_share(topology="sequential", use_llm=False)
        dist = net.run(_make_bearish_input())
        assert dist.direction == "BEARISH"

    def test_graph_does_not_crash(self):
        net = AgentNetwork._default_a_share(topology="graph", use_llm=False)
        dist = net.run(_make_bullish_input())
        assert dist.topology_used == "graph"
        total = dist.bullish_prob + dist.bearish_prob + dist.neutral_prob
        assert abs(total - 1.0) < 0.02


class TestCalibrator:
    def test_builtin_events_calibration(self):
        cal = HistoricalCalibrator(network=AgentNetwork._default_a_share(use_llm=False))
        events = cal._builtin_events()
        assert len(events) >= 4

        score = cal.calibrate(events, persist=False)
        assert score.direction_accuracy >= 0.50
        assert score.total_events == len(events)


class TestEventCatalog:
    def test_load_event_catalog_produces_50plus_events(self):
        from m11_agent_sim.event_catalog import load_event_catalog
        events = load_event_catalog(min_events=50)
        assert len(events) >= 50
        for e in events:
            assert e.event_id
            assert e.date
            assert e.market_input is not None
            assert e.actual_direction in ("BULLISH", "BEARISH", "NEUTRAL")

    def test_annotated_events_present(self):
        from m11_agent_sim.event_catalog import load_event_catalog
        events = load_event_catalog(min_events=50)
        event_ids = [e.event_id for e in events]
        assert "ev_20240924" in event_ids
        assert "ev_20241008" in event_ids

    def test_auto_events_have_price_context(self):
        from m11_agent_sim.event_catalog import load_event_catalog
        events = load_event_catalog(min_events=50)
        auto_events = [e for e in events if e.event_id.startswith("auto_")]
        if auto_events:
            e = auto_events[0]
            assert e.market_input.price.current_price > 0

    def test_estimate_sentiment(self):
        from m11_agent_sim.event_catalog import _estimate_sentiment
        fear = _estimate_sentiment("2024-09-24", "BEARISH", price_5d_chg=-0.05)
        assert fear.fear_greed_index < 50
        greed = _estimate_sentiment("2024-10-08", "BULLISH", price_5d_chg=0.05)
        assert greed.fear_greed_index > 50


class TestCalibrationStore:
    def test_save_and_load_run(self):
        from m11_agent_sim.calibration_store import CalibrationStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(db_path=Path(tmpdir) / "test_cal.db")
            run = CalibrationRun(
                run_id="test_run_001",
                run_timestamp=datetime.now(),
                market="A_SHARE",
                topology="sequential",
                n_events=50,
                score=CalibrationScore(
                    total_events=50, direction_hits=35,
                    direction_accuracy=0.70, prob_calibration_err=0.12,
                    extreme_recall=0.60, composite_score=65.0,
                    pass_threshold=True,
                ),
                cases=[
                    ValidationCase(
                        event_id="ev_001", date="2024-09-24",
                        description="test", actual_direction="BULLISH",
                        simulated_direction="BULLISH", direction_match=True,
                        actual_5d_return=0.165, simulated_bullish_prob=0.72,
                        prob_error=0.28,
                    ),
                ],
            )
            store.save_run(run)

            loaded = store.load_run("test_run_001")
            assert loaded is not None
            assert loaded.run_id == "test_run_001"
            assert loaded.n_events == 50
            assert loaded.score.pass_threshold is True
            assert len(loaded.cases) == 1
            assert loaded.cases[0].direction_match is True

    def test_list_runs(self):
        from m11_agent_sim.calibration_store import CalibrationStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(db_path=Path(tmpdir) / "test_cal2.db")
            for i in range(3):
                run = CalibrationRun(
                    run_id=f"run_{i:03d}",
                    run_timestamp=datetime.now(),
                    n_events=50 + i,
                    score=CalibrationScore(total_events=50 + i),
                )
                store.save_run(run)

            runs = store.list_runs(limit=10)
            assert len(runs) == 3

    def test_compare_runs(self):
        from m11_agent_sim.calibration_store import CalibrationStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(db_path=Path(tmpdir) / "test_cal3.db")
            run_a = CalibrationRun(
                run_id="run_a", run_timestamp=datetime.now(),
                n_events=50,
                score=CalibrationScore(total_events=50, direction_accuracy=0.65, composite_score=55.0),
            )
            run_b = CalibrationRun(
                run_id="run_b", run_timestamp=datetime.now(),
                n_events=55,
                score=CalibrationScore(total_events=55, direction_accuracy=0.72, composite_score=62.0),
            )
            store.save_run(run_a)
            store.save_run(run_b)

            comp = store.compare("run_a", "run_b")
            assert comp is not None
            assert comp["direction_accuracy_delta"] > 0
            assert comp["composite_score_delta"] > 0


class TestValidationSchemas:
    def test_validation_case_schema(self):
        vc = ValidationCase(
            event_id="ev_001", date="2024-09-24",
            description="test event", actual_direction="BULLISH",
            simulated_direction="BULLISH", direction_match=True,
        )
        assert vc.direction_match is True

    def test_calibration_run_schema(self):
        run = CalibrationRun(
            run_id="test", n_events=50,
            score=CalibrationScore(total_events=50, direction_accuracy=0.75),
            cases=[ValidationCase(event_id="e1", date="2024-01-01", description="t")],
        )
        assert run.n_events == 50
        assert len(run.cases) == 1
