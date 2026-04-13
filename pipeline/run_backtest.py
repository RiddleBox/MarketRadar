"""
pipeline/run_backtest.py — 回测 Pipeline 入口

用法：
  python pipeline/run_backtest.py --start 2024-01-01 --end 2024-06-30 --market A_SHARE
  python pipeline/run_backtest.py --start 2023-01-01 --end 2023-12-31 --market A_SHARE,HK --data-source akshare
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich import box

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schemas import Market
from core.data_loader import AKShareLoader, BaoStockLoader, CSVLoader
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from m4_action.action_designer import ActionDesigner
from m7_backtester.backtester import Backtester
from core.llm_client import LLMClient

console = Console()
logging.basicConfig(level=logging.WARNING)


@click.command()
@click.option("--start", required=True, help="回测开始日期（YYYY-MM-DD）")
@click.option("--end", required=True, help="回测结束日期（YYYY-MM-DD）")
@click.option("--market", "-m", default="A_SHARE", help="目标市场（逗号分隔）")
@click.option("--data-source", default="akshare", type=click.Choice(["akshare", "baostock", "csv"]))
@click.option("--csv-dir", default=None, help="CSV 数据目录（data-source=csv 时必填）")
@click.option("--min-intensity", default=5, help="最低信号强度（1-10，过滤低质量信号）")
@click.option("--output", "-o", default=None, help="输出回测报告 JSON 路径")
@click.option("--verbose", "-v", is_flag=True)
def run(start, end, market, data_source, csv_dir, min_intensity, output, verbose):
    """MarketRadar — 回测引擎

    从 Signal Store 加载指定时间段的信号，重新运行判断框架，
    用历史行情验证机会是否兑现。
    """

    if verbose:
        logging.getLogger().setLevel(logging.INFO)

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    markets = [Market(m.strip()) for m in market.split(",")]

    console.print(Panel(
        f"[bold cyan]MarketRadar 回测[/bold cyan]\n"
        f"区间: {start} ~ {end} | 市场: {', '.join(m.value for m in markets)} | 数据源: {data_source}",
        box=box.ROUNDED,
    ))

    # ── 初始化数据加载器 ────────────────────────────────────────
    if data_source == "akshare":
        loader = AKShareLoader()
    elif data_source == "baostock":
        loader = BaoStockLoader()
    else:
        if not csv_dir:
            console.print("[red]✗ CSV 模式需要指定 --csv-dir[/red]")
            sys.exit(1)
        loader = CSVLoader(data_dir=Path(csv_dir))

    # ── 从 Signal Store 加载历史信号 ────────────────────────────
    console.print("\n[bold]加载历史信号[/bold] ...", end=" ")
    store = SignalStore()
    signals = store.get_by_time_range(
        start=start_dt,
        end=end_dt,
        markets=markets,
        min_intensity=min_intensity,
    )
    console.print(f"[green]✓ 加载 {len(signals)} 条信号[/green]")

    if not signals:
        console.print("[yellow]⚠ 该时间段无信号记录。请先运行 run_pipeline.py 收集信号。[/yellow]")
        sys.exit(0)

    # ── 重新运行 M3 判断（严格前向隔离） ────────────────────────
    console.print("\n[bold]M3 重新判断机会[/bold] ...")
    llm_client = LLMClient()
    engine = JudgmentEngine(llm_client=llm_client)

    # 按批次分组，模拟原始运行顺序
    batch_groups: dict = {}
    for sig in sorted(signals, key=lambda s: s.event_time or datetime.min):
        bid = sig.batch_id or "unknown"
        batch_groups.setdefault(bid, []).append(sig)

    all_opportunities = []
    cumulative_signals = []  # 前向隔离：只使用已"发生"的信号

    for batch_id, batch_signals in batch_groups.items():
        opps = engine.judge(
            signals=batch_signals,
            historical_signals=cumulative_signals if cumulative_signals else None,
            batch_id=f"backtest_{batch_id}",
        )
        all_opportunities.extend(opps)
        cumulative_signals.extend(batch_signals)

    console.print(f"[green]✓ 识别 {len(all_opportunities)} 个机会[/green]")

    # ── M4 生成行动计划 ─────────────────────────────────────────
    console.print("\n[bold]M4 生成行动计划[/bold] ...")
    designer = ActionDesigner(llm_client=llm_client)
    plans = []
    for opp in all_opportunities:
        try:
            plan = designer.design(opp)
            plans.append(plan)
        except Exception as e:
            console.print(f"  [yellow]⚠ {opp.opportunity_id} 行动设计失败: {e}[/yellow]")

    console.print(f"[green]✓ 生成 {len(plans)} 个行动计划[/green]")

    # ── M7 回测执行 ─────────────────────────────────────────────
    console.print("\n[bold]M7 执行回测[/bold] ...")
    backtester = Backtester()
    report = backtester.run(
        signals=signals,
        action_plans=plans,
        opportunities=all_opportunities,
        start=start_dt,
        end=end_dt,
        data_loader=loader,
    )

    # ── 输出结果 ─────────────────────────────────────────────────
    console.print("\n")
    console.print(Panel(report.summary(), title="回测报告", box=box.ROUNDED))

    if output:
        import dataclasses
        report_dict = {
            "start": start,
            "end": end,
            "market": market,
            "total_trades": report.total_trades,
            "win_rate": report.win_rate,
            "profit_loss_ratio": report.profit_loss_ratio,
            "max_drawdown": report.max_drawdown,
            "total_return": report.total_return,
            "by_market": report.by_market,
            "by_priority": report.by_priority,
            "warnings": report.warnings,
            "trades": [
                {
                    "opportunity_id": t.opportunity_id,
                    "instrument": t.instrument,
                    "direction": t.direction,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "exit_reason": t.exit_reason,
                    "pnl_pct": t.pnl_pct,
                    "priority_level": t.priority_level,
                    "market": t.market,
                }
                for t in report.trades
            ],
        }
        Path(output).write_text(
            json.dumps(report_dict, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        console.print(f"[dim]回测报告已保存: {output}[/dim]")


if __name__ == "__main__":
    run()
