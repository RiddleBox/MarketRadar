#!/usr/bin/env python3
"""
MarketRadar 持续模拟运行

交易时段(9:30-15:00)每30分钟执行盘中扫描，
每4小时执行一次盘后全量扫描。
非交易时段自动跳过盘中扫描。
按 Ctrl+C 停止。

启动：
  python run_continuous_simulation.py
"""
import sys
import time
import signal
from datetime import datetime

from rich.console import Console

from core.schemas import Market
from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine
from m12_opportunity_catcher.anomaly_detector import AnomalyDetector
from m9_paper_trader.baostock_feed import BaostockFeed
from m9_paper_trader.eastmoney_feed import EastMoneyFeed
from m9_paper_trader.price_feed import YFinanceFeed

console = Console()

RUNNING = True


def _signal_handler(sig, frame):
    global RUNNING
    console.print("\n[yellow]收到停止信号，正在退出...[/yellow]")
    RUNNING = False


signal.signal(signal.SIGINT, _signal_handler)


def run_intraday_scan():
    now = datetime.now().strftime("%H:%M:%S")
    console.print(f"\n[bold cyan]═══ 盘中扫描 @ {now} ═══[/bold cyan]")

    markets_configs = [
        (Market.A_SHARE, EastMoneyFeed),
        (Market.HK, YFinanceFeed),
        (Market.US, YFinanceFeed),
    ]

    total = 0
    for market, feed_cls in markets_configs:
        try:
            console.print(f"  [bold]扫描 {market.value}...[/bold]")
            detector_kwargs = {}
            if market == Market.A_SHARE:
                detector_kwargs = dict(
                    sigma_threshold=2.0,
                    atr_threshold=2.0,
                    volume_threshold=1.5,
                )
            elif market in (Market.HK, Market.US):
                detector_kwargs = dict(
                    sigma_threshold=2.0,
                    atr_threshold=1.5,
                    volume_threshold=1.5,
                )

            detector = AnomalyDetector(**detector_kwargs)
            engine = OpportunityCatcherEngine(anomaly_detector=detector)
            pf = feed_cls()
            results = engine.run_intraday_scan(market=market, price_feed=pf)

            if results:
                console.print(f"  [green]✓ {market.value}: {len(results)} 个补牢机会[/green]")
                for r in results[:3]:
                    a = r.anomaly
                    console.print(
                        f"    {a.instrument} {a.price_change_pct:+.1f}% "
                        f"({a.anomaly_type}) [{r.trend.stage.value}]"
                    )
                total += len(results)
            else:
                console.print(f"  [dim]{market.value}: 无异动[/dim]")
        except Exception as e:
            console.print(f"  [yellow]⚠ {market.value} 扫描失败: {e}[/yellow]")

    console.print(f"\n  [bold]盘中总计: {total} 个补牢机会[/bold]")
    return total


def run_daily_scan():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"\n[bold green]═══ 盘后全量扫描 @ {now} ═══[/bold green]")

    markets_configs = [
        (Market.A_SHARE, BaostockFeed),
        (Market.HK, YFinanceFeed),
        (Market.US, YFinanceFeed),
    ]

    total = 0
    for market, feed_cls in markets_configs:
        try:
            console.print(f"  [bold]扫描 {market.value}...[/bold]")
            detector = AnomalyDetector(
                sigma_threshold=2.0,
                atr_threshold=2.0,
                volume_threshold=1.5,
            )
            engine = OpportunityCatcherEngine(anomaly_detector=detector)
            pf = feed_cls()
            results = engine.run_daily_scan(market=market, price_feed=pf)

            if results:
                console.print(f"\n  [bold green]{market.value}: {len(results)} 个补牢机会[/bold green]")
                for r in results:
                    a = r.anomaly
                    t = r.trend
                    c = r.causation
                    console.print(
                        f"    {a.instrument} {a.price_change_pct:+.1f}% | "
                        f"{a.anomaly_type} | {t.stage.value} | "
                        f"conf={c.confidence:.0%} | upside={t.remaining_upside_pct:.1f}%"
                    )
                total += len(results)
            else:
                console.print(f"  [dim]{market.value}: 无异动[/dim]")
        except Exception as e:
            console.print(f"  [yellow]⚠ {market.value} 扫描失败: {e}[/yellow]")

    console.print(f"\n  [bold]盘后总计: {total} 个补牢机会[/bold]")
    _save_results(total)
    return total


def _save_results(total_count):
    results_file = "data/m12_scan_results.json"
    try:
        import json
        from pathlib import Path
        Path("data").mkdir(exist_ok=True)
        record = {
            "timestamp": datetime.now().isoformat(),
            "total_opportunities": total_count,
        }
        existing = []
        if Path(results_file).exists():
            with open(results_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        if isinstance(existing, list):
            existing.append(record)
        else:
            existing = [record]

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def main():
    console.print("[bold green]╔══════════════════════════════════════════╗[/bold green]")
    console.print("[bold green]║  MarketRadar 持续模拟运行              ║[/bold green]")
    console.print("[bold green]║  盘中: 交易时段每30分钟 | 盘后: 每4小时  ║[/bold green]")
    console.print("[bold green]║  按 Ctrl+C 停止                          ║[/bold green]")
    console.print("[bold green]╚══════════════════════════════════════════╝[/bold green]")

    console.print("\n[bold]首次启动：执行盘后全量扫描...[/bold]")
    run_daily_scan()

    intraday_interval = 30 * 60
    daily_interval = 4 * 60 * 60

    last_intraday = time.time()
    last_daily = time.time()
    cycle = 0

    a_share_trading_hours = (
        (9, 30),   # 9:30 开盘
        (15, 0),   # 15:00 收盘
    )
    us_trading_hours = (
        (21, 30),  # 21:30 美股开盘 (北京时间)
        (4, 0),    # 4:00  美股收盘 (北京时间，次日)
    )

    def is_trading_time():
        now_h, now_m = datetime.now().hour, datetime.now().minute
        now_minutes = now_h * 60 + now_m
        start, end = a_share_trading_hours
        return start[0] * 60 + start[1] <= now_minutes <= end[0] * 60 + end[1]

    while RUNNING:
        time.sleep(10)
        now = time.time()

        if now - last_daily >= daily_interval:
            cycle += 1
            console.print(f"\n[dim]--- 第 {cycle} 轮盘后扫描 ---[/dim]")
            run_daily_scan()
            last_daily = now
            last_intraday = now

        elif is_trading_time() and now - last_intraday >= intraday_interval:
            cycle += 1
            console.print(f"\n[dim]--- 第 {cycle} 轮盘中扫描 (交易时段) ---[/dim]")
            run_intraday_scan()
            last_intraday = now

        if not is_trading_time() and now - last_intraday >= intraday_interval:
            console.print(f"  [dim]{datetime.now().strftime('%H:%M')} 非交易时段，跳过盘中扫描[/dim]")
            last_intraday = now

    console.print("\n[yellow]模拟运行已停止[/yellow]")


if __name__ == "__main__":
    main()