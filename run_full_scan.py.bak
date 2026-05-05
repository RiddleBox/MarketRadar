#!/usr/bin/env python3
"""Full 3-market scan with FutuFeed"""
import sys
sys.path.insert(0, ".")

from core.schemas import Market
from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine
from m12_opportunity_catcher.anomaly_detector import AnomalyDetector
from m9_paper_trader.futu_feed import FutuFeed
import json
from pathlib import Path
from datetime import datetime

detector = AnomalyDetector(sigma_threshold=2.0, atr_threshold=2.0, volume_threshold=1.5)
engine = OpportunityCatcherEngine(anomaly_detector=detector)
futu = FutuFeed()

total = 0

# A-share with FutuFeed
print("=== A-share scan (FutuFeed) ===")
r = futu.get_daily_prices("600519.SH", days=40)
if r:
    print(f"  Futu A-share kline: {len(r['prices'])} days, last={r['prices'][-1]:.2f}")
else:
    print("  Futu A-share kline: None")

results_a = engine.run_daily_scan(market=Market.A_SHARE, price_feed=futu)
print(f"  Found {len(results_a)} A-share opportunities")
for retro in results_a[:5]:
    a = retro.anomaly
    t = retro.trend
    c = retro.causation
    print(f"    {a.instrument}: {a.price_change_pct:+.1f}% | {a.anomaly_type} | {t.stage.value} | conf={c.confidence:.0%}")
total += len(results_a)

# HK with FutuFeed
print("\n=== HK scan (FutuFeed) ===")
r2 = futu.get_daily_prices("0700.HK", days=40)
if r2:
    print(f"  Futu HK kline: {len(r2['prices'])} days, last={r2['prices'][-1]:.2f}")
else:
    print("  Futu HK kline: None")

results_hk = engine.run_daily_scan(market=Market.HK, price_feed=futu)
print(f"  Found {len(results_hk)} HK opportunities")
for retro in results_hk[:5]:
    a = retro.anomaly
    t = retro.trend
    print(f"    {a.instrument}: {a.price_change_pct:+.1f}% | {a.anomaly_type} | {t.stage.value}")
total += len(results_hk)

# US with FutuFeed
print("\n=== US scan (FutuFeed) ===")
results_us = engine.run_daily_scan(market=Market.US, price_feed=futu)
print(f"  Found {len(results_us)} US opportunities")
for retro in results_us[:5]:
    a = retro.anomaly
    t = retro.trend
    print(f"    {a.instrument}: {a.price_change_pct:+.1f}% | {a.anomaly_type} | {t.stage.value}")
total += len(results_us)

futu.close()

# Save results
print(f"\n=== Total: {total} opportunities across 3 markets ===")
results_file = Path("data/m12_scan_results.json")
results_file.parent.mkdir(exist_ok=True)
existing = []
if results_file.exists():
    existing = json.load(open(results_file, encoding="utf-8"))
existing.append({
    "timestamp": datetime.now().isoformat(),
    "total_opportunities": total,
    "a_share": len(results_a),
    "hk": len(results_hk),
    "us": len(results_us),
})
with open(results_file, "w", encoding="utf-8") as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
print(f"Results saved to {results_file}")