#!/usr/bin/env python3
"""Test A-share real-time scan"""

import sys
sys.path.insert(0, '.')

from datetime import datetime
from core.schemas import Market
from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine
from m12_opportunity_catcher.anomaly_detector import AnomalyDetector
from m9_paper_trader.futu_feed import FutuFeed

def test_a_share_scan():
    """Test A-share real-time scan"""
    print(f"\n{'='*60}")
    print(f"A-share Real-time Scan Test @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # Create anomaly detector
    detector = AnomalyDetector(
        sigma_threshold=2.0,
        atr_threshold=2.0,
        volume_threshold=1.5,
    )

    # Create scan engine
    engine = OpportunityCatcherEngine(anomaly_detector=detector)

    # Create Futu data feed
    print("Connecting to Futu OpenD...")
    feed = FutuFeed()

    if not feed._connected:
        print("[ERROR] Futu OpenD not connected, please start FutuOpenD first")
        return

    print("[OK] Futu OpenD connected\n")

    # Run intraday scan
    print("Scanning A-share market...")
    results = engine.run_intraday_scan(market=Market.A_SHARE, price_feed=feed)

    print(f"\n{'='*60}")
    print(f"Scan completed: found {len(results)} opportunities")
    print(f"{'='*60}\n")

    if results:
        for i, r in enumerate(results, 1):
            a = r.anomaly
            t = r.trend
            c = r.causation
            print(f"{i}. {a.instrument}")
            print(f"   Price change: {a.price_change_pct:+.1f}%")
            print(f"   Anomaly type: {a.anomaly_type}")
            print(f"   Trend stage: {t.stage.value}")
            print(f"   Confidence: {c.confidence:.0%}")
            print(f"   Remaining upside: {t.remaining_upside_pct:.1f}%")
            print()
    else:
        print("No opportunities found at this time")

    feed.close()

if __name__ == "__main__":
    test_a_share_scan()
