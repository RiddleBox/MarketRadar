#!/usr/bin/env python3
"""
run_live_validation.py — 7天真实数据模拟验证

功能：
  1. 每天自动采集真实新闻（Xinhua/NDRC/36Kr/AKShare）
  2. M1.5 推理生成隐性信号
  3. M3 验证信号置信度
  4. 获取真实行情价格（AKShare/YFinance）
  5. M9 模拟盘开仓/平仓
  6. 每日生成报告，周末生成汇总报告

使用：
  # 单次运行（今天）
  python run_live_validation.py

  # 连续7天运行
  python run_live_validation.py --days 7

  # 指定日期范围
  python run_live_validation.py --start 2026-04-28 --end 2026-05-04

  # 仅查看报告
  python run_live_validation.py --report
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json
import time
import argparse

if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from live_signal_monitor import LiveSignalMonitor
from m9_paper_trader.paper_trader import PaperTrader
from m9_paper_trader.price_feed import AKShareRealtimeFeed, YFinanceFeed, CompositeFeed


OUTPUT_DIR = Path("live_validation")
REPORT_FILE = OUTPUT_DIR / "weekly_report.json"


def run_single_day(monitor: LiveSignalMonitor, date: str = None):
    """运行单日的真实数据验证"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    print(f"\n{'='*80}")
    print(f"真实数据验证 - {date}")
    print(f"{'='*80}\n")

    monitor.run_daily_monitoring(date)


def generate_weekly_report(output_dir: Path):
    """生成周汇总报告"""
    report_files = sorted(output_dir.glob("report_*.json"))

    if not report_files:
        print("[报告] 未找到每日报告")
        return

    all_signals = []
    all_trades = []
    daily_stats = []

    for report_file in report_files:
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)

        date = report['metadata']['date']
        stats = report['statistics']

        daily_stats.append({
            'date': date,
            'news_count': stats['news_count'],
            'signal_count': stats['signal_count'],
            'high_confidence_signals': stats['high_confidence_signals'],
            'signal_types': stats.get('signal_types', {}),
            'industry_sectors': stats.get('industry_sectors', {}),
        })

        for signal in report.get('signals', []):
            all_signals.append(signal)
            if 'paper_trade' in signal:
                all_trades.append({
                    'date': date,
                    'signal_id': signal['signal_id'],
                    'signal_type': signal['signal_type'],
                    'industry_sector': signal['industry_sector'],
                    'confidence': signal['posterior_confidence'],
                    'paper_trade': signal['paper_trade'],
                })

    # 读取模拟盘最终状态
    positions_file = Path("data/paper_positions.json")
    trade_log_file = Path("data/paper_trade_log.json")

    positions = []
    if positions_file.exists():
        with open(positions_file, 'r', encoding='utf-8') as f:
            positions = json.load(f)

    trade_log = []
    if trade_log_file.exists():
        with open(trade_log_file, 'r', encoding='utf-8') as f:
            trade_log = json.load(f)

    # 计算汇总统计
    total_signals = len(all_signals)
    high_conf_signals = len([s for s in all_signals if s.get('posterior_confidence', 0) >= 0.7])
    total_trades = len(all_trades)

    # 计算盈亏
    total_pnl = 0
    closed_positions = [p for p in positions if p.get('status') != 'OPEN']
    open_positions = [p for p in positions if p.get('status') == 'OPEN']

    for pos in closed_positions:
        pnl_pct = pos.get('realized_pnl_pct', 0) or 0
        entry_value = pos.get('entry_price', 0) * pos.get('quantity', 0)
        total_pnl += pnl_pct * entry_value

    weekly_report = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'report_period': {
                'start': daily_stats[0]['date'] if daily_stats else None,
                'end': daily_stats[-1]['date'] if daily_stats else None,
            },
            'trading_days': len(daily_stats),
        },
        'summary': {
            'total_news': sum(s['news_count'] for s in daily_stats),
            'total_signals': total_signals,
            'high_confidence_signals': high_conf_signals,
            'total_trades': total_trades,
            'realized_pnl': round(total_pnl, 2),
            'closed_positions': len(closed_positions),
            'open_positions': len(open_positions),
        },
        'daily_stats': daily_stats,
        'signals': all_signals,
        'trades': all_trades,
        'positions': {
            'closed': closed_positions,
            'open': open_positions,
        },
        'trade_log': trade_log,
    }

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(weekly_report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*80}")
    print(f"周汇总报告")
    print(f"{'='*80}")
    print(f"报告期间: {weekly_report['metadata']['report_period']['start']} ~ {weekly_report['metadata']['report_period']['end']}")
    print(f"交易天数: {weekly_report['metadata']['trading_days']}")
    print(f"新闻总数: {weekly_report['summary']['total_news']}")
    print(f"信号总数: {weekly_report['summary']['total_signals']}")
    print(f"高置信度信号: {weekly_report['summary']['high_confidence_signals']}")
    print(f"交易次数: {weekly_report['summary']['total_trades']}")
    print(f"已实现盈亏: {weekly_report['summary']['realized_pnl']:+.2f}")
    print(f"平仓次数: {weekly_report['summary']['closed_positions']}")
    print(f"当前持仓: {weekly_report['summary']['open_positions']}")
    print(f"\n报告已保存: {REPORT_FILE}")
    print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(description='7天真实数据模拟验证')
    parser.add_argument('--days', type=int, default=1, help='连续运行天数（默认1）')
    parser.add_argument('--start', type=str, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--interval', type=int, default=24, help='运行间隔（小时），默认24')
    parser.add_argument('--report', action='store_true', help='仅生成报告')
    parser.add_argument('--output-dir', type=str, default='live_validation', help='输出目录')

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    if args.report:
        generate_weekly_report(output_dir)
        return

    # 初始化监控器
    monitor = LiveSignalMonitor(output_dir=str(output_dir), enable_paper_trading=True)

    if args.start and args.end:
        # 指定日期范围
        start = datetime.strptime(args.start, '%Y-%m-%d')
        end = datetime.strptime(args.end, '%Y-%m-%d')
        current = start
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            run_single_day(monitor, date_str)
            current += timedelta(days=1)
    else:
        # 连续运行 N 天
        for i in range(args.days):
            date_str = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
            run_single_day(monitor, date_str)

            if i < args.days - 1:
                print(f"\n[等待] {args.interval} 小时后执行下一次验证...")
                try:
                    time.sleep(args.interval * 3600)
                except KeyboardInterrupt:
                    print("\n[中断] 用户停止连续验证")
                    break

    # 生成汇总报告
    generate_weekly_report(output_dir)


if __name__ == '__main__':
    main()
