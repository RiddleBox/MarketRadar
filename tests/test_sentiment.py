"""
tests/test_sentiment.py — M10 情绪面系统测试

覆盖：
  1. SentimentSnapshot 情绪计算逻辑（离线）
  2. SentimentStore CRUD + 趋势计算
  3. SentimentEngine 离线 Mock
  4. SentimentSignalData → MarketSignal schema 兼容性
  5. MockSentinelAdapter → inject_sentiment_signals 注入 M2
  6. M3 情绪校准规则（_extract_sentiment_context + _calibrate_priority）
"""
import tempfile, sys
from datetime import datetime, timedelta
from pathlib import Path

from m0_collector.providers.sentiment_provider import SentimentSnapshot, SentimentProvider
from m10_sentiment.sentiment_store import SentimentStore
from core.schemas import SignalType


class TestSentimentSnapshot:
    def test_greedy_score(self):
        snap = SentimentSnapshot(
            market_up_count=3800, market_down_count=500,
            northbound_net_flow=120.0,
            avg_comprehensive_score=72.0,
            weibo_sentiment_stocks=[("比亚迪", 0.8), ("宁德时代", 0.6), ("平安银行", -0.1)],
        )
        score = snap.fear_greed_score()
        assert score > 70
        assert snap.direction() == "BULLISH"

    def test_fearful_score(self):
        snap = SentimentSnapshot(
            market_up_count=400, market_down_count=4200,
            northbound_net_flow=-150.0,
            avg_comprehensive_score=30.0,
            weibo_sentiment_stocks=[("中概股", -0.9), ("恒生ETF", -0.7)],
        )
        score = snap.fear_greed_score()
        assert score < 30
        assert snap.direction() == "BEARISH"

    def test_neutral_score(self):
        snap = SentimentSnapshot(
            market_up_count=2200, market_down_count=2300,
            northbound_net_flow=5.0,
            avg_comprehensive_score=50.0,
        )
        score = snap.fear_greed_score()
        assert 35 < score < 65
        assert snap.direction() == "NEUTRAL"

    def test_hot_sectors(self):
        snap = SentimentSnapshot(
            baidu_hot_stocks=[("中国能建", 325000), ("包钢股份", 313000), ("比亚迪", 200000)]
        )
        hot = snap.hot_sectors()
        assert "中国能建" in hot


class TestSentimentStore:
    def _make_store(self, tmpdir):
        return SentimentStore(db_path=Path(tmpdir) / "test.db")

    def test_save_and_query(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            base_time = datetime.now() - timedelta(hours=50)
            scores = [25.0, 30.0, 35.0, 45.0, 55.0, 62.0, 68.0, 72.0, 78.0, 80.0]
            for i, s in enumerate(scores):
                store.save({
                    "snapshot_time": (base_time + timedelta(hours=i*5)).isoformat(),
                    "batch_id": f"test_{i}",
                    "fear_greed_score": s,
                    "sentiment_label": "test",
                    "direction": "BULLISH" if s > 50 else "BEARISH",
                    "northbound_net_flow": (s - 50) * 2,
                    "advance_decline_ratio": s / 100,
                    "avg_comprehensive_score": s,
                    "high_score_count": int(s / 10),
                })

            latest = store.latest(3)
            assert len(latest) == 3
            assert latest[0]["fear_greed"] == 80.0

            rows = store.query_range(base_time - timedelta(hours=1), base_time + timedelta(hours=100))
            assert len(rows) == 10

    def test_find_extremes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            base_time = datetime.now() - timedelta(hours=20)
            for i, s in enumerate([20.0, 25.0, 55.0, 70.0, 85.0]):
                store.save({
                    "snapshot_time": (base_time + timedelta(hours=i*4)).isoformat(),
                    "batch_id": f"ext_{i}",
                    "fear_greed_score": s,
                    "sentiment_label": "test",
                    "direction": "BULLISH" if s > 50 else "BEARISH",
                    "northbound_net_flow": 0,
                    "advance_decline_ratio": 0.5,
                    "avg_comprehensive_score": s,
                    "high_score_count": 0,
                })

            extremes = store.find_extremes(threshold_high=80, threshold_low=30)
            assert any(r["fear_greed"] >= 80 for r in extremes)
            assert any(r["fear_greed"] <= 30 for r in extremes)

    def test_trend(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            base_time = datetime.now() - timedelta(hours=50)
            scores = [25.0, 30.0, 35.0, 45.0, 55.0, 62.0, 68.0, 72.0, 78.0, 80.0]
            for i, s in enumerate(scores):
                store.save({
                    "snapshot_time": (base_time + timedelta(hours=i*5)).isoformat(),
                    "batch_id": f"trend_{i}",
                    "fear_greed_score": s,
                    "sentiment_label": "test",
                    "direction": "BULLISH",
                    "northbound_net_flow": 0,
                    "advance_decline_ratio": 0.5,
                    "avg_comprehensive_score": s,
                    "high_score_count": 0,
                })
            trend = store.trend(10)
            assert trend["is_rising"] is True
            assert trend["slope"] > 0


class TestSentimentSignalToMarketSignal:
    def test_mock_adapter_signals_are_schema_compatible(self):
        from integrations.market_sentinel import MockSentinelAdapter
        from core.schemas import MarketSignal

        adapter = MockSentinelAdapter(fear_greed=35.0, northbound=60.0)
        signals = adapter.fetch_and_convert(market="A_SHARE", batch_id="test_batch")
        assert len(signals) >= 1

        for sig in signals:
            d = sig.to_market_signal_dict()
            ms = MarketSignal(**d)
            assert ms.signal_type.value == "sentiment"
            assert ms.time_horizon.value == "SHORT"
            assert ms.source_type.value == "social_media"
            assert ms.signal_id.startswith("sent_")

    def test_extreme_fear_signal_direction(self):
        from integrations.market_sentinel import MockSentinelAdapter

        adapter = MockSentinelAdapter(fear_greed=15.0, northbound=-200.0)
        signals = adapter.fetch_and_convert(market="A_SHARE")
        fg_signal = [s for s in signals if "FGI" in s.signal_label or "恐惧" in s.signal_label]
        if fg_signal:
            assert fg_signal[0].signal_direction == "BULLISH"

    def test_extreme_greed_signal_direction(self):
        from integrations.market_sentinel import MockSentinelAdapter

        adapter = MockSentinelAdapter(fear_greed=90.0, northbound=150.0)
        signals = adapter.fetch_and_convert(market="A_SHARE")
        fg_signal = [s for s in signals if "FGI" in s.signal_label or "贪婪" in s.signal_label]
        if fg_signal:
            assert fg_signal[0].signal_direction == "BEARISH"


class TestInjectSentimentToM2:
    def test_inject_sentiment_signals_stores_in_m2(self):
        from integrations.market_sentinel import MockSentinelAdapter, inject_sentiment_signals
        from m2_storage.signal_store import SignalStore
        import os

        db_path = Path(tempfile.mkdtemp()) / "test_signals.db"
        os.environ["SIGNAL_STORE_DB"] = str(db_path)
        try:
            adapter = MockSentinelAdapter(fear_greed=40.0, northbound=30.0)
            signals = inject_sentiment_signals(adapter, markets=["A_SHARE"], batch_id="test_inject")
            assert len(signals) >= 1

            store = SignalStore()
            results = store.get_by_time_range(
                start=datetime.now() - timedelta(hours=1),
                end=datetime.now() + timedelta(hours=1),
                signal_types=[SignalType.SENTIMENT],
            )
            sentiment_results = [s for s in results if s.signal_type.value == "sentiment"]
            assert len(sentiment_results) >= 1
        finally:
            os.environ.pop("SIGNAL_STORE_DB", None)
            if db_path.exists():
                db_path.unlink()


class TestM3SentimentCalibration:
    def _make_score(self, overall=5.0, confidence=0.5, timeliness=5, execution_readiness=0.5, **kw):
        from core.schemas import OpportunityScore
        defaults = dict(
            catalyst_strength=5, timeliness=timeliness, market_confirmation=5,
            tradability=5, risk_clarity=5, consensus_gap=5, signal_consistency=5,
            overall_score=overall, confidence_score=confidence,
            execution_readiness=execution_readiness,
        )
        defaults.update(kw)
        return OpportunityScore(**defaults)

    def test_extreme_fear_upgrades_priority(self):
        from m3_judgment.judgment_engine import JudgmentEngine
        from core.schemas import PriorityLevel

        s = self._make_score(overall=5.5, confidence=0.6)
        ctx = {"fear_greed_index": 15.0, "sentiment_label": "极度恐惧", "signal_ids": ["sent_001"]}
        result = JudgmentEngine._calibrate_priority("research", s, sentiment_context=ctx)
        assert result == PriorityLevel.POSITION.value

    def test_extreme_greed_downgrades_priority(self):
        from m3_judgment.judgment_engine import JudgmentEngine
        from core.schemas import PriorityLevel

        s = self._make_score(overall=7.0, confidence=0.7)
        ctx = {"fear_greed_index": 85.0, "sentiment_label": "极度贪婪", "signal_ids": ["sent_002"]}
        result = JudgmentEngine._calibrate_priority("position", s, sentiment_context=ctx)
        assert result == PriorityLevel.RESEARCH.value

    def test_neutral_sentiment_no_change(self):
        from m3_judgment.judgment_engine import JudgmentEngine

        s = self._make_score(overall=6.5, confidence=0.6, execution_readiness=0.7)
        ctx = {"fear_greed_index": 50.0, "sentiment_label": "中性", "signal_ids": ["sent_003"]}
        result = JudgmentEngine._calibrate_priority("research", s, sentiment_context=ctx)
        assert result == "research"

    def test_no_sentiment_context_no_change(self):
        from m3_judgment.judgment_engine import JudgmentEngine

        s = self._make_score(overall=6.5, confidence=0.6, execution_readiness=0.7)
        result = JudgmentEngine._calibrate_priority("research", s, sentiment_context=None)
        assert result == "research"

    def test_extreme_fear_low_score_no_upgrade(self):
        from m3_judgment.judgment_engine import JudgmentEngine
        from core.schemas import PriorityLevel

        s = self._make_score(overall=3.5, confidence=0.5)
        ctx = {"fear_greed_index": 15.0, "sentiment_label": "极度恐惧", "signal_ids": ["sent_004"]}
        result = JudgmentEngine._calibrate_priority("watch", s, sentiment_context=ctx)
        assert result == PriorityLevel.WATCH.value

    def test_extract_sentiment_context_with_fear_greed_in_description(self):
        from m3_judgment.judgment_engine import JudgmentEngine
        from core.schemas import MarketSignal, SignalType, Direction, SourceType, Market, TimeHorizon, SignalLogicFrame

        sig = MarketSignal(
            signal_id="sent_test001",
            signal_type=SignalType.SENTIMENT,
            signal_label="市场情绪: 极度恐惧（恐贪指数 18）",
            description="【市场情绪面快照】恐贪指数: 18.0/100 — 极度恐惧",
            evidence_text="FGI=18, 北向资金=-80亿",
            affected_markets=[Market.A_SHARE],
            signal_direction=Direction.BEARISH,
            event_time=datetime.now(),
            time_horizon=TimeHorizon.SHORT,
            intensity_score=8,
            confidence_score=7,
            timeliness_score=9,
            source_type=SourceType.SOCIAL_MEDIA,
            source_ref="market_sentinel",
            logic_frame=SignalLogicFrame(
                what_changed="情绪面: 极度恐惧",
                change_direction=Direction.BEARISH,
                affects=["A股整体"],
            ),
        )
        ctx = JudgmentEngine._extract_sentiment_context([sig])
        assert ctx is not None
        assert ctx["fear_greed_index"] == 18.0
        assert "恐惧" in ctx["sentiment_label"]

    def test_extract_sentiment_context_returns_none_without_sentiment(self):
        from m3_judgment.judgment_engine import JudgmentEngine
        from core.schemas import MarketSignal, SignalType, Direction, SourceType, Market, TimeHorizon, SignalLogicFrame

        sig = MarketSignal(
            signal_id="sig_policy001",
            signal_type=SignalType.POLICY,
            signal_label="央行降准0.5个百分点",
            description="央行宣布降准",
            evidence_text="央行公告",
            affected_markets=[Market.A_SHARE],
            signal_direction=Direction.BULLISH,
            event_time=datetime.now(),
            time_horizon=TimeHorizon.MEDIUM,
            intensity_score=7,
            confidence_score=8,
            timeliness_score=9,
            source_type=SourceType.POLICY_DOCUMENT,
            source_ref="pbc.gov",
            logic_frame=SignalLogicFrame(
                what_changed="存款准备金率下调0.5个百分点",
                change_direction=Direction.BULLISH,
                affects=["银行股", "地产股"],
            ),
        )
        ctx = JudgmentEngine._extract_sentiment_context([sig])
        assert ctx is None
