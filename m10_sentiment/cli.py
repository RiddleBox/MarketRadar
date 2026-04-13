"""
m10_sentiment/cli.py — 情绪面 CLI

用法：
    python -m m10_sentiment.cli run          # 采集一次并输出
    python -m m10_sentiment.cli run --inject # 采集 + 注入 M2
    python -m m10_sentiment.cli history      # 查看历史快照
    python -m m10_sentiment.cli trend        # 情绪趋势
    python -m m10_sentiment.cli extremes     # 历史极值点
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def cmd_run(args):
    from m10_sentiment.sentiment_engine import SentimentEngine
    from m10_sentiment.sentiment_store import SentimentStore

    engine = SentimentEngine()
    print("正在采集情绪数据（约 5~10 秒）...")

    if args.inject:
        signal = engine.run_and_inject()
    else:
        signal = engine.run()

    if signal is None:
        print("❌ 情绪采集失败")
        return

    print()
    print("=" * 60)
    print(f"  {signal.signal_label}")
    print("=" * 60)
    print(f"  恐贪指数:   {signal.fear_greed_index:.1f} / 100")
    print(f"  情绪方向:   {signal.signal_direction}")
    print(f"  信号强度:   {signal.intensity_score:.1f} / 10")
    print(f"  信号置信:   {signal.confidence_score:.1f} / 10")
    print()
    print(signal.description)
    print()
    if signal.hot_sectors:
        print(f"  🔥 热门标的: {', '.join(signal.hot_sectors)}")
    if args.inject:
        print("  ✅ 已注入 M2 信号库")

    # 保存到 SentimentStore
    store = SentimentStore()
    snap_data = {
        "snapshot_time": (signal.event_time or datetime.now()).isoformat(),
        "batch_id": signal.batch_id,
        "fear_greed_score": signal.fear_greed_index,
        "sentiment_label": signal.sentiment_label,
        "direction": signal.signal_direction,
    }
    store.save(snap_data)


def cmd_history(args):
    from m10_sentiment.sentiment_store import SentimentStore
    store = SentimentStore()
    rows = store.latest(args.n)
    if not rows:
        print("暂无历史记录，请先运行: python -m m10_sentiment.cli run")
        return

    print(f"\n{'时间':<22} {'恐贪指数':>8} {'标签':<12} {'方向':<10} {'北向(亿)':>10}")
    print("-" * 72)
    for r in rows:
        t = r.get("snapshot_time", "?")[:19]
        fg = r.get("fear_greed", 50)
        label = r.get("label", "?")
        direction = r.get("direction", "?")
        flow = r.get("northbound_flow", 0)
        flow_str = f"{flow:+.1f}" if flow else "—"
        bar = "▓" * int(fg / 10) + "░" * (10 - int(fg / 10))
        print(f"  {t:<20} {fg:>6.1f}  [{bar}] {label:<12} {direction:<10} {flow_str:>10}")


def cmd_trend(args):
    from m10_sentiment.sentiment_store import SentimentStore
    store = SentimentStore()
    t = store.trend(args.n)
    if t["count"] == 0:
        print("暂无数据")
        return

    print(f"\n情绪趋势（最近 {t['count']} 次）")
    print(f"  当前: {t['current']:.1f}  上次: {t['prev']:.1f}  均值: {t['avg_score']:.1f}")
    trend_arrow = "📈 上升" if t["is_rising"] else "📉 下降"
    print(f"  趋势: {trend_arrow}  斜率: {t['slope']:+.3f}")


def cmd_extremes(args):
    from m10_sentiment.sentiment_store import SentimentStore
    store = SentimentStore()
    rows = store.find_extremes()
    if not rows:
        print("暂无极值记录")
        return

    print(f"\n历史情绪极值（共 {len(rows)} 次）")
    print(f"{'时间':<22} {'恐贪指数':>8} {'标签':<12}")
    print("-" * 50)
    for r in rows[:10]:
        t = r.get("snapshot_time", "?")[:19]
        fg = r.get("fear_greed", 50)
        label = r.get("label", "?")
        emoji = "🔴 极贪婪" if fg >= 80 else "🟢 极恐惧"
        print(f"  {t:<20} {fg:>6.1f}  {label:<12} {emoji}")


def main():
    parser = argparse.ArgumentParser(description="MarketRadar 情绪面 CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="采集情绪数据")
    p_run.add_argument("--inject", action="store_true", help="注入 M2 信号库")

    p_hist = sub.add_parser("history", help="查看历史快照")
    p_hist.add_argument("-n", type=int, default=10, help="显示条数")

    p_trend = sub.add_parser("trend", help="情绪趋势")
    p_trend.add_argument("-n", type=int, default=10, help="计算最近 N 次")

    sub.add_parser("extremes", help="历史极值点")

    args = parser.parse_args()
    if args.cmd == "run":
        cmd_run(args)
    elif args.cmd == "history":
        cmd_history(args)
    elif args.cmd == "trend":
        cmd_trend(args)
    elif args.cmd == "extremes":
        cmd_extremes(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
