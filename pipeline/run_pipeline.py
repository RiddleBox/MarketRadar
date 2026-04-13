"""
pipeline/run_pipeline.py — 端到端 Pipeline 运行入口

用法：
  python pipeline/run_pipeline.py --input data/incoming/sample.txt --market A_SHARE,HK
  python pipeline/run_pipeline.py --input data/incoming/sample.txt --batch-id batch_001 --verbose
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
from rich.table import Table
from rich import box

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schemas import Market, SourceType
from core.llm_client import LLMClient
from m1_decoder.decoder import SignalDecoder
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from m4_action.action_designer import ActionDesigner

console = Console()
logging.basicConfig(level=logging.WARNING)


@click.command()
@click.option("--input", "-i", "input_file", required=True, help="输入文本文件路径")
@click.option("--market", "-m", default="A_SHARE,HK", help="目标市场（逗号分隔，如 A_SHARE,HK）")
@click.option("--batch-id", default=None, help="批次 ID（默认自动生成）")
@click.option("--source-type", default="news", help="信息源类型（news/report/announcement）")
@click.option("--source-ref", default="manual_input", help="来源标识")
@click.option("--verbose", "-v", is_flag=True, help="显示详细日志")
@click.option("--dry-run", is_flag=True, help="仅解码信号，不进行机会判断")
@click.option("--output", "-o", default=None, help="输出 JSON 文件路径（可选）")
def run(input_file, market, batch_id, source_type, source_ref, verbose, dry_run, output):
    """MarketRadar — 端到端 Pipeline 运行"""

    if verbose:
        logging.getLogger().setLevel(logging.INFO)

    batch_id = batch_id or f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # ── 读取输入 ────────────────────────────────────────────────
    input_path = Path(input_file)
    if not input_path.exists():
        console.print(f"[red]✗ 输入文件不存在: {input_file}[/red]")
        sys.exit(1)

    raw_text = input_path.read_text(encoding="utf-8")
    markets = [Market(m.strip()) for m in market.split(",")]

    console.print(Panel(
        f"[bold cyan]MarketRadar Pipeline[/bold cyan]\n"
        f"批次: {batch_id} | 市场: {', '.join(m.value for m in markets)} | 输入: {input_file}",
        box=box.ROUNDED,
    ))

    # ── M1 信号解码 ─────────────────────────────────────────────
    console.print("\n[bold]M1 信号解码[/bold] ...", end=" ")
    llm_client = LLMClient()
    decoder = SignalDecoder(llm_client=llm_client)

    try:
        signals = decoder.decode(
            raw_text=raw_text,
            source_ref=source_ref,
            source_type=SourceType(source_type),
            batch_id=batch_id,
        )
        console.print(f"[green]✓ 提取 {len(signals)} 条信号[/green]")
    except Exception as e:
        console.print(f"[red]✗ 解码失败: {e}[/red]")
        sys.exit(1)

    if not signals:
        console.print("[yellow]⚠ 未提取到有效信号，pipeline 终止[/yellow]")
        sys.exit(0)

    # 打印信号摘要
    _print_signals_table(signals)

    # ── M2 信号存储 ─────────────────────────────────────────────
    console.print("\n[bold]M2 信号存储[/bold] ...", end=" ")
    store = SignalStore()
    saved = store.save(signals)
    console.print(f"[green]✓ 保存 {saved} 条（去重后）[/green]")

    if dry_run:
        console.print("\n[yellow]--dry-run 模式，跳过 M3/M4[/yellow]")
        _maybe_save_output({"batch_id": batch_id, "signals": [s.model_dump(mode="json") for s in signals]}, output)
        return

    # ── M3 机会判断 ─────────────────────────────────────────────
    console.print("\n[bold]M3 机会判断[/bold] ...", end=" ")
    engine = JudgmentEngine(llm_client=llm_client)

    # 检索历史相关信号（最近 90 天）
    from datetime import timedelta
    hist_start = datetime.now() - timedelta(days=90)
    hist_signals = store.get_by_time_range(
        start=hist_start,
        end=datetime.now(),
        markets=markets,
        min_intensity=5,
    )
    # 排除当前批次（避免重复）
    current_ids = {s.signal_id for s in signals}
    hist_signals = [s for s in hist_signals if s.signal_id not in current_ids]

    opportunities = engine.judge(
        signals=signals,
        historical_signals=hist_signals if hist_signals else None,
        batch_id=batch_id,
    )

    if not opportunities:
        console.print("[yellow]⚠ 当前批次未发现机会（信号已保留，将参与后续批次组合）[/yellow]")
    else:
        console.print(f"[green]✓ 发现 {len(opportunities)} 个机会[/green]")
        _print_opportunities_table(opportunities)

    # ── M4 行动设计 ─────────────────────────────────────────────
    if opportunities:
        console.print("\n[bold]M4 行动设计[/bold] ...")
        designer = ActionDesigner(llm_client=llm_client)
        plans = []
        for opp in opportunities:
            plan = designer.design(opp)
            plans.append(plan)
            console.print(f"  ✓ [{opp.priority_level.value}] {opp.opportunity_title} → {plan.instrument}")

        # 保存机会到 data/opportunities/
        _save_opportunities(opportunities, batch_id)
    else:
        plans = []

    # ── 输出结果 ─────────────────────────────────────────────────
    result = {
        "batch_id": batch_id,
        "run_time": datetime.now().isoformat(),
        "signals_count": len(signals),
        "opportunities_count": len(opportunities),
        "plans_count": len(plans),
        "signals": [s.model_dump(mode="json") for s in signals],
        "opportunities": [o.model_dump(mode="json") for o in opportunities],
        "plans": [p.model_dump(mode="json") for p in plans],
    }

    _maybe_save_output(result, output)

    console.print(Panel(
        f"[bold green]Pipeline 完成[/bold green]\n"
        f"信号: {len(signals)} | 机会: {len(opportunities)} | 行动计划: {len(plans)}",
        box=box.ROUNDED,
    ))


def _print_signals_table(signals):
    table = Table(title="信号列表", box=box.SIMPLE)
    table.add_column("ID", style="dim")
    table.add_column("类型")
    table.add_column("标签")
    table.add_column("市场")
    table.add_column("方向")
    table.add_column("强度/置信/时效", justify="center")

    for s in signals:
        markets = "/".join([m.value for m in s.affected_markets])
        table.add_row(
            s.signal_id,
            s.signal_type.value,
            s.signal_label[:30],
            markets,
            s.signal_direction.value,
            f"{s.intensity_score}/{s.confidence_score}/{s.timeliness_score}",
        )
    console.print(table)


def _print_opportunities_table(opportunities):
    table = Table(title="机会列表", box=box.SIMPLE)
    table.add_column("ID", style="dim")
    table.add_column("标题", style="bold")
    table.add_column("优先级", justify="center")
    table.add_column("市场")
    table.add_column("方向")
    table.add_column("时机")

    priority_colors = {
        "watch": "dim", "research": "yellow",
        "position": "green", "urgent": "bold red",
    }

    for opp in opportunities:
        markets = "/".join([m.value for m in opp.target_markets])
        color = priority_colors.get(opp.priority_level.value, "white")
        table.add_row(
            opp.opportunity_id,
            opp.opportunity_title[:25],
            f"[{color}]{opp.priority_level.value}[/{color}]",
            markets,
            opp.trade_direction.value,
            opp.why_now[:40] if opp.why_now else "",
        )
    console.print(table)


def _save_opportunities(opportunities, batch_id):
    opp_dir = Path(__file__).parent.parent / "data" / "opportunities"
    opp_dir.mkdir(parents=True, exist_ok=True)
    out_file = opp_dir / f"{batch_id}_opportunities.json"
    data = [o.model_dump(mode="json") for o in opportunities]
    out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _maybe_save_output(result, output_path):
    if output_path:
        Path(output_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        console.print(f"\n[dim]结果已保存: {output_path}[/dim]")


if __name__ == "__main__":
    run()
