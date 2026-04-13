"""
m9_paper_trader/cli.py — 模拟盘命令行工具

用法：
  # 查看当前模拟持仓
  python -m m9_paper_trader.cli status

  # 手动开立模拟持仓
  python -m m9_paper_trader.cli open --inst 510300.SH --mkt A_SHARE --dir BULLISH \\
      --entry 3.85 --sl 3.65 --tp 4.23 --qty 10000

  # 批量更新价格（从 AKShare）
  python -m m9_paper_trader.cli update

  # 手动平仓
  python -m m9_paper_trader.cli close --id pp_xxxx --price 4.10

  # 生成信号有效性评估报告
  python -m m9_paper_trader.cli evaluate

  # 到期清理（超过N天的 OPEN 仓标记为 EXPIRED）
  python -m m9_paper_trader.cli expire --days 90
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def cmd_status(args, trader):
    open_pos = trader.list_open()
    closed_pos = trader.list_closed()
    print(f"\n{'='*60}")
    print(f"模拟盘状态  |  开仓: {len(open_pos)}  |  已关闭: {len(closed_pos)}")
    print(f"{'='*60}")

    if open_pos:
        print("\n📌 持仓中：")
        for pp in open_pos:
            pnl = pp.unrealized_pnl_pct * 100
            color = "▲" if pnl >= 0 else "▼"
            print(f"  {pp.paper_position_id:15} | {pp.instrument:12} | {pp.direction:8}"
                  f" | 入场={pp.entry_price:.3f} | 现价={pp.current_price:.3f}"
                  f" | {color}{abs(pnl):.2f}%"
                  f" | 止损={pp.stop_loss_price:.3f}"
                  f" | 强度={pp.signal_intensity:.0f} 置信={pp.signal_confidence:.0f}")
    else:
        print("\n  暂无持仓中的模拟仓")

    if closed_pos and args.all:
        print(f"\n📋 已关闭（最近 20 条）：")
        for pp in sorted(closed_pos, key=lambda x: x.exit_time or x.entry_time, reverse=True)[:20]:
            pnl = (pp.realized_pnl_pct or 0) * 100
            color = "▲" if pnl >= 0 else "▼"
            print(f"  {pp.paper_position_id:15} | {pp.instrument:12} | {pp.status:12}"
                  f" | {color}{abs(pnl):.2f}%  | {pp.signal_type}")


def cmd_open(args, trader):
    pp = trader.open_manual(
        instrument=args.inst,
        market=args.mkt,
        direction=args.dir.upper(),
        entry_price=args.entry,
        stop_loss_price=args.sl,
        take_profit_price=args.tp,
        quantity=args.qty,
        signal_intensity=args.intensity,
        signal_confidence=args.confidence,
        signal_type=args.signal_type or "",
    )
    print(f"✓ 模拟仓已开立: {pp.paper_position_id}")
    print(f"  品种: {pp.instrument}  方向: {pp.direction}")
    print(f"  入场: {pp.entry_price}  止损: {pp.stop_loss_price}  止盈: {pp.take_profit_price}")


def cmd_update(args, trader):
    from m9_paper_trader.price_feed import make_price_feed
    feed = make_price_feed(mode=args.feed, csv_path=args.csv or "")
    result = trader.update_all_prices(feed)
    print(f"✓ 更新 {result['updated']} 个持仓")
    if result["closed"]:
        print(f"  触发平仓: {result['closed']}")


def cmd_close(args, trader):
    ok = trader.close_manual(args.id, args.price)
    print(f"{'✓' if ok else '✗'} 平仓 {args.id} @ {args.price}")


def cmd_evaluate(args, trader):
    from m9_paper_trader.evaluator import SignalEvaluator
    all_pos = trader.list_all()
    closed = trader.list_closed()
    print(f"\n总持仓: {len(all_pos)}  |  已关闭: {len(closed)}")

    evaluator = SignalEvaluator()
    report = evaluator.evaluate(closed, min_closed=args.min_closed)
    path = evaluator.save_report(report)

    overall = report.get("overall", {})
    grade = report.get("signal_efficacy_grade", {})

    print(f"\n{'='*60}")
    print(f"  信号有效性评级: {grade.get('grade', 'N/A')}  — {grade.get('description', '')}")
    print(f"{'='*60}")
    print(f"  胜率: {overall.get('win_rate', 'N/A')}%")
    print(f"  期望值: {overall.get('expectancy_pct', 'N/A')}%/笔")
    print(f"  盈亏比: {overall.get('profit_factor', 'N/A')}")
    print(f"  Sharpe: {overall.get('sharpe', 'N/A')}")

    if report.get("recommendations"):
        print("\n💡 改进建议：")
        for r in report["recommendations"]:
            print(f"  • {r}")

    if report.get("by_signal_type"):
        print("\n📊 按信号类型：")
        for k, v in report["by_signal_type"].items():
            print(f"  {k:15} | 胜率 {v.get('win_rate', 0)}% | 期望 {v.get('expectancy_pct', 0):+.2f}% | n={v.get('count', 0)}")

    print(f"\n报告已保存: {path}")


def cmd_expire(args, trader):
    expired = trader.expire_old(max_days=args.days)
    print(f"✓ 标记为 EXPIRED: {len(expired)} 条")
    for pid in expired:
        print(f"  {pid}")


def main():
    parser = argparse.ArgumentParser(description="MarketRadar 模拟盘管理")
    sub = parser.add_subparsers(dest="cmd")

    # status
    p_status = sub.add_parser("status", help="查看模拟持仓状态")
    p_status.add_argument("--all", action="store_true", help="同时显示已关闭持仓")

    # open
    p_open = sub.add_parser("open", help="手动开立模拟持仓")
    p_open.add_argument("--inst", required=True, help="品种代码，如 510300.SH")
    p_open.add_argument("--mkt", default="A_SHARE", help="市场 A_SHARE/HK/US")
    p_open.add_argument("--dir", default="BULLISH", help="方向 BULLISH/BEARISH")
    p_open.add_argument("--entry", type=float, required=True, help="入场价")
    p_open.add_argument("--sl", type=float, required=True, help="止损价")
    p_open.add_argument("--tp", type=float, default=None, help="止盈价（可选）")
    p_open.add_argument("--qty", type=float, default=10000, help="模拟数量")
    p_open.add_argument("--intensity", type=float, default=0, help="信号强度（0-10）")
    p_open.add_argument("--confidence", type=float, default=0, help="信号置信度（0-10）")
    p_open.add_argument("--signal-type", default="", help="信号类型")

    # update
    p_update = sub.add_parser("update", help="批量更新价格（AKShare）")
    p_update.add_argument("--feed", default="akshare", choices=["akshare", "csv"])
    p_update.add_argument("--csv", default="", help="CSV 文件路径（feed=csv 时）")

    # close
    p_close = sub.add_parser("close", help="手动平仓")
    p_close.add_argument("--id", required=True, help="paper_position_id")
    p_close.add_argument("--price", type=float, required=True, help="平仓价格")

    # evaluate
    p_eval = sub.add_parser("evaluate", help="生成信号有效性评估报告")
    p_eval.add_argument("--min-closed", type=int, default=5, help="最少关闭持仓数")

    # expire
    p_expire = sub.add_parser("expire", help="将超期持仓标记为 EXPIRED")
    p_expire.add_argument("--days", type=int, default=90, help="超过N天标记为过期")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    from m9_paper_trader.paper_trader import PaperTrader
    trader = PaperTrader()

    dispatch = {
        "status": cmd_status,
        "open": cmd_open,
        "update": cmd_update,
        "close": cmd_close,
        "evaluate": cmd_evaluate,
        "expire": cmd_expire,
    }
    dispatch[args.cmd](args, trader)


if __name__ == "__main__":
    main()
