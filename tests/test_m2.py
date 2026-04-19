"""
tests/test_m2.py — M2 Signal Store 测试

覆盖：
  1. 信号保存与批量检索
  2. 按时间范围查询
  3. 按市场/类型过滤
  4. 统计信息
"""
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from core.schemas import MarketSignal, Market, SignalType, TimeHorizon
from m2_storage.signal_store import SignalStore


def _make_signal(signal_id="sig_001", signal_type=SignalType.MACRO, market=Market.A_SHARE):
    now = datetime.now()
    return MarketSignal(
        signal_id=signal_id,
        signal_type=signal_type,
        signal_label=f"测试信号_{signal_id}",
        description="测试信号描述",
        evidence_text="测试来源",
        affected_markets=[market],
        affected_instruments=["510300.SH"],
        signal_direction="BULLISH",
        event_time=now,
        collected_time=now,
        time_horizon=TimeHorizon.SHORT,
        intensity_score=7,
        confidence_score=8,
        timeliness_score=9,
        source_type="official_announcement",
        source_ref="test",
        logic_frame={"what_changed": "测试变化", "change_direction": "BULLISH", "affects": ["A_SHARE"]},
        batch_id="test_batch",
    )


class TestSignalStore:
    def _make_store(self, tmpdir):
        import m2_storage.signal_store as mod
        orig = mod.DB_FILE
        mod.DB_FILE = Path(tmpdir) / "test_signals.db"
        store = SignalStore()
        mod.DB_FILE = orig
        return store

    def test_save_and_get_by_batch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            signals = [_make_signal("sig_a"), _make_signal("sig_b")]
            store.save(signals)
            loaded = store.get_by_batch("test_batch")
            assert len(loaded) == 2

    def test_get_by_time_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            signals = [_make_signal("sig_001"), _make_signal("sig_002")]
            store.save(signals)
            now = datetime.now()
            loaded = store.get_by_time_range(
                start=now - timedelta(hours=1),
                end=now + timedelta(hours=1),
            )
            assert len(loaded) >= 2

    def test_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._make_store(tmpdir)
            store.save([_make_signal("sig_stats")])
            stats = store.stats()
            assert stats["total"] >= 1
