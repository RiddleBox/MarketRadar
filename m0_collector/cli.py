"""
m0_collector/cli.py — 收集器 CLI 入口

用法：
  # RSS 抓取，写入 data/incoming/
  python -m m0_collector.cli --source rss

  # 只抓取不写入（dry-run）
  python -m m0_collector.cli --source rss --dry-run

  # 手动输入单文件
  python -m m0_collector.cli --source manual --file path/to/article.txt

  # 手动粘贴文本（从 stdin）
  python -m m0_collector.cli --source manual

  # 抓取后立即触发 pipeline/ingest（--then-ingest）
  python -m m0_collector.cli --source rss --then-ingest --market A_SHARE,HK
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from m0_collector.dedup import DedupIndex
from m0_collector.normalizer import Normalizer
from m0_collector.providers.manual import ManualProvider
from m0_collector.providers.rss import RssProvider

console = Console()
logging.basicConfig(level=logging.WARNING)

INCOMING_DIR = ROOT / "data" / "incoming"
DEDUP_INDEX_PATH = ROOT / "m0_collector" / "manifest" / "dedup_index.json"


@click.command()
@click.option("--source", "-s", default="rss",
              type=click.Choice(["rss", "manual"]),
              help="数据来源（rss / manual）")
@click.option("--file", "-f", "input_file", default=None,
              help="手动模式：指定输入文件路径")
@click.option("--text", "-t", default=None,
              help="手动模式：直接传入文本内容")
@click.option("--limit", "-n", default=None, type=int,
              help="最多处理 N 条（调试用）")
@click.option("--dry-run", is_flag=True,
              help="试运行：不写入文件，只展示抓取结果")
@click.option("--force-reimport", is_flag=True,
              help="跳过去重检查（慎用）")
@click.option("--then-ingest", is_flag=True,
              help="收集完成后立即触发 pipeline/ingest（M1→M2）")
@click.option("--then-judge", is_flag=True,
              help="收集+ingestion 完成后立即触发 M3 判断（需配合 --then-ingest）")
@click.option("--market", "-m", default="A_SHARE,HK",
              help="市场标签（供 --then-ingest 使用）")
@click.option("--verbose", "-v", is_flag=True)
def run(source, input_file, text, limit, dry_run, force_reimport,
        then_ingest, then_judge, market, verbose):
    """MarketRadar M0 — 财经新闻收集器

    从 RSS 或手动输入收集财经新闻，写入 data/incoming/，
    后续由 pipeline/ingest.py 处理进入 M1→M2→M3 信号分析流程。
    """
    if verbose:
        logging.getLogger().setLevel(logging.INFO)

    INCOMING_DIR.mkdir(parents=True, exist_ok=True)

    console.print(Panel(
        f"[bold cyan]MarketRadar M0 收集器[/bold cyan]\n"
        f"来源: {source} | 市场: {market}"
        + (" | [yellow]DRY-RUN[/yellow]" if dry_run else ""),
        box=box.ROUNDED,
    ))

    # ── 选择 Provider ─────────────────────────────────────────
    if source == "rss":
        provider = RssProvider()
    else:
        provider = ManualProvider()

    # ── 抓取 ──────────────────────────────────────────────────
    console.print(f"\n[bold]抓取数据[/bold] ({provider.display_name}) ...", end=" ")
    try:
        fetch_kwargs = {}
        if limit:
            fetch_kwargs["limit"] = limit
        if input_file:
            fetch_kwargs["file"] = input_file
        if text:
            fetch_kwargs["text"] = text

        articles = provider.fetch(**fetch_kwargs)
        console.print(f"[green]✓ {len(articles)} 条原始文章[/green]")
    except Exception as e:
        console.print(f"[red]✗ 抓取失败: {e}[/red]")
        sys.exit(1)

    if not articles:
        console.print("[yellow]⚠ 没有抓取到任何内容[/yellow]")
        sys.exit(0)

    # ── 标准化 + 去重 ──────────────────────────────────────────
    dedup = DedupIndex(DEDUP_INDEX_PATH)
    normalizer = Normalizer(dedup_index=dedup)
    items, skip_count, error_count = normalizer.normalize(
        articles, force_reimport=force_reimport
    )

    console.print(
        f"标准化: [green]{len(items)} 条新内容[/green] | "
        f"去重跳过: [dim]{skip_count}[/dim] | "
        f"错误: {'[red]' + str(error_count) + '[/red]' if error_count else str(error_count)}"
    )

    if not items:
        console.print("[yellow]⚠ 全部去重或出错，无新内容写入[/yellow]")
        sys.exit(0)

    # ── 预览 ──────────────────────────────────────────────────
    preview = Table(box=box.SIMPLE)
    preview.add_column("来源")
    preview.add_column("标题")
    preview.add_column("时间")
    preview.add_column("文件名", style="dim")
    for item in items[:10]:
        preview.add_row(
            item.source_name,
            item.title[:35] + ("…" if len(item.title) > 35 else ""),
            item.published_at.strftime("%m-%d %H:%M"),
            item.filename(),
        )
    if len(items) > 10:
        preview.add_row("...", f"（共 {len(items)} 条）", "", "")
    console.print(preview)

    # ── 写入 data/incoming/ ────────────────────────────────────
    if dry_run:
        console.print("[yellow]DRY-RUN：不写入文件[/yellow]")
    else:
        written = 0
        for item in items:
            fp = INCOMING_DIR / item.filename()
            if fp.exists() and not force_reimport:
                continue
            fp.write_text(item.to_text(), encoding="utf-8")
            written += 1
        dedup.save()
        console.print(f"[green]✓ 写入 {written} 个文件到 {INCOMING_DIR}[/green]")

        # ── 可选：触发 ingestion ───────────────────────────────
        if then_ingest and written > 0:
            _trigger_ingest(market=market, then_judge=then_judge)


def _trigger_ingest(market: str, then_judge: bool):
    """收集完成后调用 pipeline/ingest.py 核心逻辑"""
    from datetime import timedelta
    from core.schemas import Market
    from core.llm_client import LLMClient
    from m1_decoder.decoder import SignalDecoder
    from m2_storage.signal_store import SignalStore
    from pipeline.ingest import collect_files, ingest_file, infer_source_type
    import json

    console.print("\n[bold]--then-ingest: 触发 M1→M2 Ingestion...[/bold]")

    batch_id = f"collect_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    markets = [Market(m.strip()) for m in market.split(",")]

    llm_client = LLMClient()
    decoder = SignalDecoder(llm_client=llm_client)
    store = SignalStore()

    files = collect_files(INCOMING_DIR)
    console.print(f"  incoming/ 中找到 {len(files)} 个文件")

    total_signals = 0
    for fp in files:
        result = ingest_file(
            file_path=fp,
            decoder=decoder,
            store=store,
            batch_id=batch_id,
            source_type=infer_source_type(fp),
            markets_str=market,
        )
        if result["error"]:
            console.print(f"  [red]✗ {fp.name}: {result['error']}[/red]")
        else:
            console.print(f"  ✓ {fp.name}: {result['signals']} 条信号")
            total_signals += result["signals"]

    console.print(f"[green]Ingestion 完成: {total_signals} 条信号[/green]")

    if then_judge and total_signals > 0:
        _trigger_judgment(store, markets, batch_id)


def _trigger_judgment(store, markets, batch_id: str):
    """Ingestion 后触发 M3 判断"""
    from datetime import timedelta
    from m3_judgment.judgment_engine import JudgmentEngine
    from m4_action.action_designer import ActionDesigner
    from core.llm_client import LLMClient
    import json

    console.print("\n[bold]--then-judge: 触发 M3 机会判断...[/bold]")

    llm_client = LLMClient()
    signals = store.get_by_batch(batch_id)
    hist = store.get_by_time_range(
        start=datetime.now() - timedelta(days=90),
        end=datetime.now(),
        markets=markets,
        min_intensity=5,
    )
    current_ids = {s.signal_id for s in signals}
    hist = [s for s in hist if s.signal_id not in current_ids]

    opps = JudgmentEngine(llm_client=llm_client).judge(
        signals=signals, historical_signals=hist or None, batch_id=batch_id
    )

    if not opps:
        console.print("[yellow]M3: 未发现机会[/yellow]")
        return

    designer = ActionDesigner(llm_client=llm_client)
    for opp in opps:
        plan = designer.design(opp)
        console.print(
            f"  [green][{opp.priority_level.value}][/green] {opp.opportunity_title} "
            f"→ {', '.join(plan.primary_instruments[:2])}"
        )

    opp_dir = ROOT / "data" / "opportunities"
    opp_dir.mkdir(parents=True, exist_ok=True)
    out = opp_dir / f"{batch_id}_opportunities.json"
    out.write_text(
        json.dumps([o.model_dump(mode="json") for o in opps], ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    console.print(f"[dim]机会已保存: {out}[/dim]")


if __name__ == "__main__":
    run()
