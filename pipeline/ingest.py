"""
pipeline/ingest.py — 批量 ingestion CLI

从目录批量读取多个文本文件，逐一喂给 M1 解码，信号写入 M2 Signal Store。
支持超长文本自动分块（按段落/句子分块，避免超出 LLM 上下文限制）。

用法：
  python pipeline/ingest.py --dir data/incoming/ --market A_SHARE,HK
  python pipeline/ingest.py --dir data/incoming/ --market A_SHARE --source-type news --dry-run
  python pipeline/ingest.py --file data/incoming/sample.txt --market A_SHARE
  python pipeline/ingest.py --dir data/incoming/ --then-judge   # ingestion 后直接跑 M3 判断
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich import box

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.schemas import Market, SourceType
from core.llm_client import LLMClient
from m1_decoder.decoder import SignalDecoder
from m2_storage.signal_store import SignalStore

console = Console()
logging.basicConfig(level=logging.WARNING)

# 每次送给 LLM 的最大字符数（约 4000 tokens，留 buffer 给 prompt 和输出）
MAX_CHUNK_CHARS = 6000
# 分块时的段落最小长度（太短的段落不单独处理）
MIN_PARAGRAPH_CHARS = 50


# ──────────────────────────────────────────────────────────────────────────────
# 文本分块逻辑
# ──────────────────────────────────────────────────────────────────────────────

def split_text_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """
    将长文本分割为适合 LLM 处理的块。

    策略（优先级从高到低）：
    1. 如果文本不超过 max_chars，直接返回 [text]
    2. 按段落（空行分隔）分块，多个短段落合并为一个块
    3. 如果单段落超过 max_chars，按句子（。！？.!?）进一步分割

    Args:
        text: 原始文本
        max_chars: 每块最大字符数

    Returns:
        文本块列表
    """
    if len(text) <= max_chars:
        return [text]

    # 按段落分割
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: List[str] = []
    current_chunk_parts: List[str] = []
    current_len = 0

    for para in paragraphs:
        # 单段落超限：先存下当前 chunk，再按句子切割这个段落
        if len(para) > max_chars:
            if current_chunk_parts:
                chunks.append("\n\n".join(current_chunk_parts))
                current_chunk_parts = []
                current_len = 0
            chunks.extend(_split_paragraph_by_sentence(para, max_chars))
            continue

        # 加入当前段落后超限：先存下当前 chunk
        if current_len + len(para) + 2 > max_chars and current_chunk_parts:
            chunks.append("\n\n".join(current_chunk_parts))
            current_chunk_parts = []
            current_len = 0

        current_chunk_parts.append(para)
        current_len += len(para) + 2  # +2 for \n\n

    if current_chunk_parts:
        chunks.append("\n\n".join(current_chunk_parts))

    return [c for c in chunks if len(c) >= MIN_PARAGRAPH_CHARS]


def _split_paragraph_by_sentence(paragraph: str, max_chars: int) -> List[str]:
    """将超长段落按句子分割"""
    import re
    sentences = re.split(r'(?<=[。！？.!?])', paragraph)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: List[str] = []
    current = ""

    for sent in sentences:
        if len(current) + len(sent) > max_chars:
            if current:
                chunks.append(current.strip())
            current = sent
        else:
            current += sent

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [paragraph[:max_chars]]


# ──────────────────────────────────────────────────────────────────────────────
# 文件列表收集
# ──────────────────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".txt", ".md", ".text"}


def collect_files(directory: Path, recursive: bool = False) -> List[Path]:
    """收集目录下所有支持的文本文件"""
    files: List[Path] = []
    pattern = "**/*" if recursive else "*"
    for f in sorted(directory.glob(pattern)):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(f)
    return files


def infer_source_type(file_path: Path, default: str = "news") -> str:
    """
    从文件名推断来源类型。
    命名约定：report_xxx.txt / announcement_xxx.txt / news_xxx.txt
    """
    name = file_path.stem.lower()
    for st in ["report", "announcement", "data", "social_media"]:
        if name.startswith(st) or f"_{st}" in name:
            return st
    return default


# ──────────────────────────────────────────────────────────────────────────────
# 核心 ingestion 函数
# ──────────────────────────────────────────────────────────────────────────────

def ingest_file(
    file_path: Path,
    decoder: SignalDecoder,
    store: SignalStore,
    batch_id: str,
    source_type: str,
    markets_str: str,
    dry_run: bool = False,
) -> dict:
    """
    处理单个文件：读取 → 分块 → M1 解码 → M2 存储

    Returns:
        { "file": str, "chunks": int, "signals": int, "saved": int, "error": Optional[str] }
    """
    result = {
        "file": file_path.name,
        "chunks": 0,
        "signals": 0,
        "saved": 0,
        "error": None,
    }

    try:
        raw_text = file_path.read_text(encoding="utf-8")
        if not raw_text.strip():
            result["error"] = "文件为空"
            return result

        # 分块
        chunks = split_text_into_chunks(raw_text)
        result["chunks"] = len(chunks)

        # 逐块解码
        all_signals = []
        for i, chunk in enumerate(chunks):
            chunk_source_ref = f"{file_path.name}#chunk{i+1}" if len(chunks) > 1 else file_path.name
            stype = SourceType(source_type) if source_type else SourceType(infer_source_type(file_path))

            if dry_run:
                # dry-run：只计数，不真正调用 LLM
                result["signals"] += len(chunk.split("。"))  # 粗估
                continue

            signals = decoder.decode(
                raw_text=chunk,
                source_ref=chunk_source_ref,
                source_type=stype,
                batch_id=batch_id,
            )
            all_signals.extend(signals)

        if not dry_run:
            result["signals"] = len(all_signals)
            if all_signals:
                saved = store.save(all_signals)
                result["saved"] = saved
            else:
                result["saved"] = 0

    except Exception as e:
        result["error"] = str(e)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# CLI 命令
# ──────────────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--dir", "-d", "input_dir", default=None, help="输入目录（批量模式）")
@click.option("--file", "-f", "input_file", default=None, help="单文件模式")
@click.option("--market", "-m", default="A_SHARE,HK", help="目标市场（逗号分隔）")
@click.option("--source-type", default="", help="来源类型（auto/news/report/announcement，默认从文件名推断）")
@click.option("--batch-id", default=None, help="批次 ID（默认自动生成）")
@click.option("--recursive", "-r", is_flag=True, help="递归处理子目录")
@click.option("--dry-run", is_flag=True, help="试运行，不调用 LLM，只扫描文件")
@click.option("--then-judge", is_flag=True, help="ingestion 完成后立即运行 M3 机会判断")
@click.option("--max-chunk-chars", default=MAX_CHUNK_CHARS, help=f"每块最大字符数（默认 {MAX_CHUNK_CHARS}）")
@click.option("--verbose", "-v", is_flag=True)
def run(input_dir, input_file, market, source_type, batch_id, recursive, dry_run, then_judge, max_chunk_chars, verbose):
    """MarketRadar — 批量 Ingestion Pipeline

    将目录中的文本文件批量送入 M1 信号解码，结果写入 M2 Signal Store。

    支持大文件自动分块，文件名约定推断来源类型。
    """
    if verbose:
        logging.getLogger().setLevel(logging.INFO)

    if not input_dir and not input_file:
        console.print("[red]✗ 请指定 --dir 或 --file[/red]")
        sys.exit(1)

    batch_id = batch_id or f"ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    markets = [Market(m.strip()) for m in market.split(",")]

    # ── 收集文件列表 ─────────────────────────────────────────
    files: List[Path] = []
    if input_file:
        p = Path(input_file)
        if not p.exists():
            console.print(f"[red]✗ 文件不存在: {input_file}[/red]")
            sys.exit(1)
        files = [p]
    else:
        d = Path(input_dir)
        if not d.exists():
            console.print(f"[red]✗ 目录不存在: {input_dir}[/red]")
            sys.exit(1)
        files = collect_files(d, recursive=recursive)
        if not files:
            console.print(f"[yellow]⚠ 目录中没有找到支持的文本文件（.txt/.md）[/yellow]")
            sys.exit(0)

    console.print(Panel(
        f"[bold cyan]MarketRadar Ingestion[/bold cyan]\n"
        f"批次: {batch_id} | 文件数: {len(files)} | 市场: {', '.join(m.value for m in markets)}"
        + (" | [yellow]DRY-RUN[/yellow]" if dry_run else ""),
        box=box.ROUNDED,
    ))

    # ── 文件列表预览 ─────────────────────────────────────────
    if verbose or len(files) <= 10:
        preview = Table(box=box.SIMPLE)
        preview.add_column("文件", style="dim")
        preview.add_column("大小")
        preview.add_column("推断来源类型")
        for f in files:
            size_kb = f.stat().st_size / 1024
            inferred = source_type or infer_source_type(f)
            preview.add_row(f.name, f"{size_kb:.1f} KB", inferred)
        console.print(preview)

    # ── 初始化组件 ───────────────────────────────────────────
    store = SignalStore()
    if not dry_run:
        llm_client = LLMClient()
        decoder = SignalDecoder(llm_client=llm_client)
    else:
        decoder = None

    # ── 批量处理 ─────────────────────────────────────────────
    results = []
    total_signals = 0
    total_saved = 0
    failed_files = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("处理文件...", total=len(files))

        for file_path in files:
            progress.update(task, description=f"[cyan]{file_path.name}[/cyan]")
            result = ingest_file(
                file_path=file_path,
                decoder=decoder,
                store=store,
                batch_id=batch_id,
                source_type=source_type or infer_source_type(file_path),
                markets_str=market,
                dry_run=dry_run,
            )
            results.append(result)
            total_signals += result["signals"]
            total_saved += result["saved"]
            if result["error"]:
                failed_files.append((file_path.name, result["error"]))
            progress.advance(task)

    # ── 结果汇总表 ───────────────────────────────────────────
    console.print()
    summary = Table(title="Ingestion 结果汇总", box=box.SIMPLE_HEAVY)
    summary.add_column("文件", style="dim")
    summary.add_column("分块数", justify="center")
    summary.add_column("信号数", justify="center")
    summary.add_column("已存储", justify="center")
    summary.add_column("状态")

    for r in results:
        status = "[red]✗ " + (r["error"] or "")[:30] if r["error"] else "[green]✓"
        summary.add_row(
            r["file"],
            str(r["chunks"]),
            str(r["signals"]),
            str(r["saved"]) if not dry_run else "-",
            status,
        )
    console.print(summary)

    # 总计行
    console.print(Panel(
        f"文件: {len(files)} | 信号总计: {total_signals}"
        + (f" | 写入 Signal Store: {total_saved}" if not dry_run else " | [yellow]DRY-RUN，未写入[/yellow]")
        + (f"\n[red]失败: {len(failed_files)} 个文件[/red]" if failed_files else ""),
        box=box.ROUNDED,
    ))

    if failed_files:
        console.print("\n[red]失败文件详情：[/red]")
        for fname, err in failed_files:
            console.print(f"  {fname}: {err}")

    # ── 可选：ingestion 完成后立即运行 M3 ────────────────────
    if then_judge and not dry_run and total_saved > 0:
        console.print("\n[bold]--then-judge: 触发 M3 机会判断...[/bold]")
        _run_judgment_after_ingest(store, markets, batch_id)


def _run_judgment_after_ingest(store: SignalStore, markets: List[Market], batch_id: str):
    """ingestion 后立即运行 M3 判断"""
    from m3_judgment.judgment_engine import JudgmentEngine
    from m4_action.action_designer import ActionDesigner
    from datetime import timedelta

    llm_client = LLMClient()
    engine = JudgmentEngine(llm_client=llm_client)
    designer = ActionDesigner(llm_client=llm_client)

    # 加载本批次信号
    signals = store.get_by_batch(batch_id)
    if not signals:
        console.print("[yellow]⚠ 当前批次无信号可判断[/yellow]")
        return

    # 历史信号（最近 90 天，过滤掉本批次）
    hist_signals = store.get_by_time_range(
        start=datetime.now() - timedelta(days=90),
        end=datetime.now(),
        markets=markets,
        min_intensity=5,
    )
    current_ids = {s.signal_id for s in signals}
    hist_signals = [s for s in hist_signals if s.signal_id not in current_ids]

    console.print(f"  当前批次信号: {len(signals)} 条 | 历史参考信号: {len(hist_signals)} 条")

    opportunities = engine.judge(
        signals=signals,
        historical_signals=hist_signals or None,
        batch_id=batch_id,
    )

    if not opportunities:
        console.print("[yellow]  M3: 当前批次未发现机会（信号已保留）[/yellow]")
        return

    console.print(f"[green]  M3: 发现 {len(opportunities)} 个机会[/green]")

    # 保存机会并生成行动计划
    opp_dir = ROOT / "data" / "opportunities"
    opp_dir.mkdir(parents=True, exist_ok=True)
    out_file = opp_dir / f"{batch_id}_opportunities.json"
    out_file.write_text(
        json.dumps([o.model_dump(mode="json") for o in opportunities], ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    for opp in opportunities:
        plan = designer.design(opp)
        priority_color = {"urgent": "red", "position": "green", "research": "yellow", "watch": "dim"}.get(
            opp.priority_level.value, "white"
        )
        console.print(
            f"  [{priority_color}][{opp.priority_level.value}][/{priority_color}] "
            f"{opp.opportunity_title} → {plan.instrument}"
        )

    console.print(f"\n[dim]机会已保存: {out_file}[/dim]")


if __name__ == "__main__":
    run()
