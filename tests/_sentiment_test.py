"""
tests/_sentiment_test.py — 情绪面系统测试

覆盖：
  1. SentimentSnapshot 情绪计算逻辑（离线，不需要网络）
  2. SentimentStore CRUD + 趋势计算
  3. SentimentEngine 集成测试（离线 mock）
  4. 情绪信号注入 M2 测试
  5. 情绪极值反转逻辑
  6. 真实 AKShare 采集（需要网络，失败则 skip）
"""
import sys, tempfile, logging
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, r'D:\AIproject\MarketRadar')
logging.basicConfig(level=logging.WARNING)


# ─────────────────────────────────────────────────────────────
print("=" * 60)
print("测试1: SentimentSnapshot 情绪计算（离线）")
print("=" * 60)

from m0_collector.providers.sentiment_provider import SentimentSnapshot, SentimentProvider

snap_greedy = SentimentSnapshot(
    market_up_count=3800, market_down_count=500,
    northbound_net_flow=120.0,
    avg_comprehensive_score=72.0,
    weibo_sentiment_stocks=[("比亚迪", 0.8), ("宁德时代", 0.6), ("平安银行", -0.1)],
)
score_g = snap_greedy.fear_greed_score()
assert score_g > 70, f"极度贪婪得分应>70，实际={score_g:.1f}"
print(f"✓ 极度贪婪场景: {score_g:.1f} → {snap_greedy.sentiment_label()}")

snap_fearful = SentimentSnapshot(
    market_up_count=400, market_down_count=4200,
    northbound_net_flow=-150.0,
    avg_comprehensive_score=30.0,
    weibo_sentiment_stocks=[("中概股", -0.9), ("恒生ETF", -0.7)],
)
score_f = snap_fearful.fear_greed_score()
assert score_f < 30, f"极度恐惧得分应<30，实际={score_f:.1f}"
print(f"✓ 极度恐惧场景: {score_f:.1f} → {snap_fearful.sentiment_label()}")

snap_neutral = SentimentSnapshot(
    market_up_count=2200, market_down_count=2300,
    northbound_net_flow=5.0,
    avg_comprehensive_score=50.0,
)
score_n = snap_neutral.fear_greed_score()
assert 35 < score_n < 65, f"中性场景应在35~65，实际={score_n:.1f}"
print(f"✓ 中性场景: {score_n:.1f} → {snap_neutral.sentiment_label()}")

assert snap_greedy.direction() == "BULLISH"
assert snap_fearful.direction() == "BEARISH"
assert snap_neutral.direction() == "NEUTRAL"
print("✓ direction() 判断正确")

snap_hot = SentimentSnapshot(
    baidu_hot_stocks=[("中国能建", 325000), ("包钢股份", 313000), ("比亚迪", 200000)]
)
hot = snap_hot.hot_sectors()
assert "中国能建" in hot
print(f"✓ hot_sectors(): {hot}")


# ─────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("测试2: SentimentStore CRUD + 趋势计算")
print("=" * 60)

from m10_sentiment.sentiment_store import SentimentStore

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
    store = SentimentStore(db_path=Path(tmpdir) / "test.db")

    base_time = datetime.now() - timedelta(hours=50)
    scores = [25.0, 30.0, 35.0, 45.0, 55.0, 62.0, 68.0, 72.0, 78.0, 80.0]
    for i, s in enumerate(scores):
        row_id = store.save({
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
    assert row_id == 10
    print(f"✓ 写入 {len(scores)} 条记录")

    latest = store.latest(3)
    assert len(latest) == 3
    assert latest[0]["fear_greed"] == 80.0
    print(f"✓ latest(3): 最新={latest[0]['fear_greed']}")

    rows = store.query_range(base_time - timedelta(hours=1), base_time + timedelta(hours=100))
    assert len(rows) == 10
    print(f"✓ query_range: {len(rows)} 条")

    extremes = store.find_extremes(threshold_high=80, threshold_low=30)
    assert any(r["fear_greed"] >= 80 for r in extremes)
    assert any(r["fear_greed"] <= 30 for r in extremes)
    print(f"✓ find_extremes: {len(extremes)} 条极值")

    trend = store.trend(10)
    assert trend["is_rising"] is True
    assert trend["slope"] > 0
    assert trend["count"] == 10
    print(f"✓ trend: 斜率={trend['slope']:+.3f}, 上升={trend['is_rising']}")

    stats = store.stats()
    assert stats["total_snapshots"] == 10
    print(f"✓ stats: {stats['total_snapshots']} 条, 均值={stats['avg_fear_greed']}")
    del store


# ─────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("测试3: SentimentEngine 离线 Mock 测试")
print("=" * 60)

from m10_sentiment.sentiment_engine import SentimentEngine


class MockSentimentProvider(SentimentProvider):
    def fetch(self):
        return SentimentSnapshot(
            market_up_count=3200, market_down_count=1100,
            northbound_net_flow=85.0,
            avg_comprehensive_score=65.0,
            baidu_hot_stocks=[("中国能建", 325000), ("包钢股份", 313000)],
            weibo_sentiment_stocks=[("比亚迪", 0.7), ("宁德时代", 0.5)],
            errors=[],
        )


engine = SentimentEngine.__new__(SentimentEngine)
engine.provider = MockSentimentProvider()

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
    import m10_sentiment.sentiment_engine as mod
    orig_root = mod.ROOT
    mod.ROOT = Path(tmpdir)
    try:
        signal = engine.run(batch_id="test_batch")
    finally:
        mod.ROOT = orig_root

assert signal is not None
assert signal.signal_type == "sentiment"
assert signal.fear_greed_index > 50
assert signal.signal_direction == "BULLISH"
assert signal.intensity_score > 0
assert signal.confidence_score >= 9.0
print(f"✓ SentimentEngine.run(): FG={signal.fear_greed_index:.1f}, 方向={signal.signal_direction}")
print(f"  标签: {signal.sentiment_label}  热门: {signal.hot_sectors}")


# ─────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("测试4: 情绪信号注入 M2（离线 Mock）")
print("=" * 60)

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
    import m10_sentiment.sentiment_engine as smod
    import m2_storage.signal_store as ssmod

    orig_root_s = smod.ROOT
    smod.ROOT = Path(tmpdir)
    orig_db = ssmod.DB_FILE
    ssmod.DB_FILE = Path(tmpdir) / "signals.db"

    engine2 = SentimentEngine.__new__(SentimentEngine)
    engine2.provider = MockSentimentProvider()

    try:
        result_signal = engine2.run(batch_id="inject_test", save_snapshot=False)
        from m2_storage.signal_store import SignalStore
        from core.schemas import MarketSignal
        ms = MarketSignal(**result_signal.to_market_signal_dict())
        store_m2 = SignalStore()
        store_m2.save([ms])
        loaded = store_m2.get_by_batch("inject_test")
        assert len(loaded) >= 1
        assert loaded[0].signal_type.value == "sentiment"
        del store_m2
        print(f"✓ 情绪信号注入 M2: signal_id={loaded[0].signal_id}")
    finally:
        smod.ROOT = orig_root_s
        ssmod.DB_FILE = orig_db


# ─────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("测试5: 情绪极值反转逻辑")
print("=" * 60)

snap_panic = SentimentSnapshot(
    market_up_count=300, market_down_count=4500,
    northbound_net_flow=-180.0,
    avg_comprehensive_score=22.0,
    weibo_sentiment_stocks=[("A50ETF", -0.95), ("沪深300ETF", -0.85)],
)
score_panic = snap_panic.fear_greed_score()
is_extreme = score_panic <= 20 or score_panic >= 80
intensity = engine._compute_intensity(score_panic)
print(f"  恐慌场景: FG={score_panic:.1f}, 极值={is_extreme}, 强度={intensity:.1f}")
assert is_extreme, f"极端恐惧应被标记为极值，FG={score_panic:.1f}"
assert intensity >= 8.0
print("✓ 极度恐惧正确标记为极值（高强度信号）")

snap_greed_max = SentimentSnapshot(
    market_up_count=4500, market_down_count=200,
    northbound_net_flow=200.0,
    avg_comprehensive_score=88.0,
    weibo_sentiment_stocks=[("沪深300ETF", 0.98), ("科创50ETF", 0.95)],
)
score_max = snap_greed_max.fear_greed_score()
intensity_max = engine._compute_intensity(score_max)
print(f"  极度贪婪: FG={score_max:.1f}, 强度={intensity_max:.1f}")
assert intensity_max >= 8.0
print("✓ 极度贪婪也标记为高强度（反转警示）")


# ─────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("测试6: 真实 AKShare 采集（需要网络，失败则 skip）")
print("=" * 60)

try:
    provider = SentimentProvider()
    print("正在采集真实情绪数据（约 5~10 秒）...")
    snap_real = provider.fetch()

    print(f"  北向净流入: {snap_real.northbound_net_flow:+.1f}亿")
    print(f"  涨跌比: {snap_real.advance_decline_ratio:.2%}")
    print(f"  均综合得分: {snap_real.avg_comprehensive_score:.1f}")
    if snap_real.baidu_hot_stocks:
        top = snap_real.baidu_hot_stocks[0]
        print(f"  百度热搜#1: {top[0]} (热度{top[1]:.0f})")
    score_real = snap_real.fear_greed_score()
    print(f"\n  ✅ 实时恐贪指数: {score_real:.1f} ({snap_real.sentiment_label()})")
    if snap_real.errors:
        print(f"  ⚠ 部分失败: {snap_real.errors}")
    else:
        print("  全部数据源采集成功")
except Exception as e:
    print(f"⏭  网络采集失败，跳过: {e}")


print()
print("=" * 60)
print("✅ 情绪面系统测试全部通过")
print("=" * 60)
print()
print("  运行实时采集:")
print("    python -m m10_sentiment.cli run")
print("  采集并注入 M2:")
print("    python -m m10_sentiment.cli run --inject")
print("  查看历史趋势:")
print("    python -m m10_sentiment.cli trend")
