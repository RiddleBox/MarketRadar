#!/usr/bin/env python3
"""
MarketRadar 每日自动化流程

用法：
  # 盘前（09:00）：采集信号 → 生成机会列表
  python run_daily_pipeline.py --mode premarket

  # 盘中（10:00/14:00）：更新价格 → 检查止损止盈
  python run_daily_pipeline.py --mode intraday

  # 盘后（15:30）：复盘归因 → 更新知识库
  python run_daily_pipeline.py --mode postmarket

  # 自动判断当前阶段
  python run_daily_pipeline.py --mode auto

定时任务配置（crontab）：
  # 盘前（周一到周五 09:00）
  0 9 * * 1-5 cd /path/to/MarketRadar && python run_daily_pipeline.py --mode premarket

  # 盘中（周一到周五 10:00, 14:00）
  0 10,14 * * 1-5 cd /path/to/MarketRadar && python run_daily_pipeline.py --mode intraday

  # 盘后（周一到周五 15:30）
  30 15 * * 1-5 cd /path/to/MarketRadar && python run_daily_pipeline.py --mode postmarket
"""
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.workflows import WorkflowPhase, resolve_phase, PHASE_STEPS
from core.schemas import Market, SourceType
from core.llm_client import LLMClient
from m0_collector.providers.rss import RssProvider
from m0_collector.dedup import DedupIndex
from m0_collector.normalizer import Normalizer
from m1_decoder.decoder import SignalDecoder
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from m10_sentiment.sentiment_provider import SentimentProvider

console = Console()

ROOT = Path(__file__).parent
INCOMING_DIR = ROOT / "data" / "incoming"
DEDUP_INDEX_PATH = ROOT / "m0_collector" / "manifest" / "dedup_index.json"


def print_header(phase: str):
    """打印阶段标题"""
    phase_names = {
        "premarket": "盘前流程（Pre-Market）",
        "intraday": "盘中流程（Intraday）",
        "postmarket": "盘后流程（Post-Market）",
    }
    console.print(Panel(
        f"[bold cyan]MarketRadar 每日自动化流程[/bold cyan]\n"
        f"阶段: {phase_names.get(phase, phase)} | 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        box=box.ROUNDED,
    ))


def step_m0_collect(limit: int = None) -> int:
    """M0: 采集隔夜新闻和公告"""
    console.print("\n[bold cyan]步骤 1/5: M0 采集隔夜信号[/bold cyan]")

    INCOMING_DIR.mkdir(parents=True, exist_ok=True)

    # 使用RSS Provider
    provider = RssProvider()
    console.print(f"  数据源: {provider.display_name}")

    try:
        # 抓取数据
        fetch_kwargs = {}
        if limit:
            fetch_kwargs["limit"] = limit

        raw_items = provider.fetch(**fetch_kwargs)
        console.print(f"  ✓ 抓取到 {len(raw_items)} 条原始数据")

        # 去重
        dedup = DedupIndex(index_path=DEDUP_INDEX_PATH)
        unique_items = dedup.filter_new(raw_items)
        console.print(f"  ✓ 去重后剩余 {len(unique_items)} 条")

        if not unique_items:
            console.print("  [yellow]无新数据，跳过后续步骤[/yellow]")
            return 0

        # 标准化
        normalizer = Normalizer()
        normalized = [normalizer.normalize(item) for item in unique_items]

        # 写入文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for i, doc in enumerate(normalized):
            filename = f"{timestamp}_{i:03d}.txt"
            filepath = INCOMING_DIR / filename
            filepath.write_text(doc.content, encoding="utf-8")

        console.print(f"  ✓ 写入 {len(normalized)} 个文件到 {INCOMING_DIR}")

        # 更新去重索引
        dedup.add_batch(unique_items)
        dedup.save()

        return len(normalized)

    except Exception as e:
        console.print(f"  [red]✗ M0 采集失败: {e}[/red]")
        return 0


def step_m10_sentiment() -> dict:
    """M10: 采集情绪面快照"""
    console.print("\n[bold cyan]步骤 2/5: M10 情绪面快照[/bold cyan]")

    try:
        provider = SentimentProvider()
        snapshot = provider.get_latest_snapshot()

        console.print(f"  ✓ 恐贪指数: {snapshot.fear_greed_index}")
        console.print(f"  ✓ 北向资金: {snapshot.northbound_flow_1d:+.2f}亿")

        return {
            "fear_greed_index": snapshot.fear_greed_index,
            "northbound_flow": snapshot.northbound_flow_1d,
        }

    except Exception as e:
        console.print(f"  [yellow]⚠ M10 采集失败（非致命）: {e}[/yellow]")
        return {}


def step_m1_decode(markets: list[Market]) -> list:
    """M1: 解码信号"""
    console.print("\n[bold cyan]步骤 3/5: M1 信号解码[/bold cyan]")

    # 读取incoming目录下的所有文件
    files = sorted(INCOMING_DIR.glob("*.txt"))
    if not files:
        console.print("  [yellow]无待处理文件[/yellow]")
        return []

    console.print(f"  待处理文件: {len(files)} 个")

    llm_client = LLMClient()
    decoder = SignalDecoder(llm_client=llm_client)

    all_signals = []
    batch_id = f"daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    for i, file_path in enumerate(files, 1):
        try:
            raw_text = file_path.read_text(encoding="utf-8")

            signals = decoder.decode(
                raw_text=raw_text,
                source_ref=file_path.name,
                source_type=SourceType.NEWS,
                batch_id=batch_id,
            )

            all_signals.extend(signals)
            console.print(f"  [{i}/{len(files)}] {file_path.name}: {len(signals)} 条信号")

        except Exception as e:
            console.print(f"  [red]✗ 解码失败 {file_path.name}: {e}[/red]")
            continue

    console.print(f"  ✓ 总计提取 {len(all_signals)} 条信号")
    return all_signals


def step_m2_store(signals: list) -> int:
    """M2: 存储信号"""
    console.print("\n[bold cyan]步骤 4/5: M2 信号存储[/bold cyan]")

    if not signals:
        console.print("  [yellow]无信号需要存储[/yellow]")
        return 0

    try:
        store = SignalStore()
        saved = store.save(signals)
        console.print(f"  ✓ 保存 {saved} 条信号（去重后）")
        return saved

    except Exception as e:
        console.print(f"  [red]✗ M2 存储失败: {e}[/red]")
        return 0


def step_m3_judge(markets: list[Market], lookback_days: int = 7) -> list:
    """M3: 机会判断"""
    console.print("\n[bold cyan]步骤 5/5: M3 机会判断（推理引擎）[/bold cyan]")

    try:
        llm_client = LLMClient()
        store = SignalStore()
        engine = JudgmentEngine(llm_client=llm_client, signal_store=store)

        # 获取最近N天的信号
        recent_signals = store.query(
            markets=markets,
            limit=100,
            lookback_days=lookback_days,
        )

        console.print(f"  输入信号: {len(recent_signals)} 条（最近{lookback_days}天）")

        # 判断机会
        opportunities = engine.judge(
            signals=recent_signals,
            markets=markets,
        )

        console.print(f"  ✓ 识别机会: {len(opportunities)} 个")

        # 打印机会摘要
        if opportunities:
            table = Table(title="今日机会列表", box=box.SIMPLE)
            table.add_column("优先级", style="cyan")
            table.add_column("市场", style="green")
            table.add_column("机会摘要", style="white")
            table.add_column("推理事件", style="yellow")

            for opp in opportunities:
                # 提取推理事件摘要
                inferred_summary = ""
                if opp.inferred_events:
                    inferred_summary = f"{len(opp.inferred_events)}个预测事件"

                table.add_row(
                    opp.opportunity_priority.value,
                    opp.market.value,
                    opp.opportunity_thesis[:60] + "...",
                    inferred_summary,
                )

            console.print(table)

        return opportunities

    except Exception as e:
        console.print(f"  [red]✗ M3 判断失败: {e}[/red]")
        return []


def run_premarket(markets: list[Market], limit: int = None):
    """盘前流程：采集 → 解码 → 判断"""
    print_header("premarket")

    # Step 1: M0 采集
    collected = step_m0_collect(limit=limit)
    if collected == 0:
        console.print("\n[yellow]无新数据，流程结束[/yellow]")
        return

    # Step 2: M10 情绪面
    sentiment = step_m10_sentiment()

    # Step 3: M1 解码
    signals = step_m1_decode(markets=markets)
    if not signals:
        console.print("\n[yellow]未提取到信号，流程结束[/yellow]")
        return

    # Step 4: M2 存储
    saved = step_m2_store(signals)
    if saved == 0:
        console.print("\n[yellow]无新信号，流程结束[/yellow]")
        return

    # Step 5: M3 判断
    opportunities = step_m3_judge(markets=markets)

    # 总结
    console.print("\n" + "=" * 70)
    console.print("[bold green]盘前流程完成[/bold green]")
    console.print(f"  采集: {collected} 条")
    console.print(f"  信号: {len(signals)} 条")
    console.print(f"  存储: {saved} 条")
    console.print(f"  机会: {len(opportunities)} 个")

    if opportunities:
        console.print("\n[bold yellow]⚠️  请人工审核机会列表，决定是否执行[/bold yellow]")
        console.print("   查看详情: python pipeline/dashboard.py")

    console.print("=" * 70)


def run_intraday(markets: list[Market]):
    """盘中流程：更新价格 → 检查止损止盈"""
    print_header("intraday")

    console.print("\n[bold cyan]盘中流程[/bold cyan]")
    console.print("  [yellow]TODO: 实现盘中价格更新和止损止盈监控[/yellow]")
    console.print("  功能包括:")
    console.print("    1. 更新M9模拟盘持仓价格")
    console.print("    2. 检查止损/止盈触发条件")
    console.print("    3. 采集盘中新增信号（可选）")
    console.print("    4. 实时推送告警（可选）")


def run_postmarket(markets: list[Market]):
    """盘后流程：复盘归因 → 更新知识库"""
    print_header("postmarket")

    console.print("\n[bold cyan]盘后流程[/bold cyan]")
    console.print("  [yellow]TODO: 实现盘后复盘和知识库更新[/yellow]")
    console.print("  功能包括:")
    console.print("    1. M6 复盘归因（分析今日持仓表现）")
    console.print("    2. M8 知识库更新（沉淀经验教训）")
    console.print("    3. M11 Agent校准（可选）")
    console.print("    4. 生成次日关注列表")


@click.command()
@click.option("--mode", "-m",
              type=click.Choice(["auto", "premarket", "intraday", "postmarket"]),
              default="auto",
              help="运行模式（auto=自动判断当前阶段）")
@click.option("--market", default="A_SHARE,HK",
              help="目标市场（逗号分隔）")
@click.option("--limit", type=int, default=None,
              help="M0采集限制条数（调试用）")
@click.option("--verbose", "-v", is_flag=True,
              help="显示详细日志")
def main(mode, market, limit, verbose):
    """MarketRadar 每日自动化流程

    自动执行盘前/盘中/盘后工作流，包括：
    - 盘前：采集信号 → 解码 → 判断机会
    - 盘中：更新价格 → 检查止损止盈
    - 盘后：复盘归因 → 更新知识库
    """

    # 解析市场
    markets = [Market(m.strip()) for m in market.split(",")]

    # 自动判断阶段
    if mode == "auto":
        phase = resolve_phase(market="A_SHARE")
        if phase == WorkflowPhase.PRE_MARKET:
            mode = "premarket"
        elif phase == WorkflowPhase.INTRADAY:
            mode = "intraday"
        elif phase == WorkflowPhase.POST_MARKET:
            mode = "postmarket"
        else:
            console.print("[yellow]当前非交易时段，退出[/yellow]")
            return

    # 执行对应阶段
    try:
        if mode == "premarket":
            run_premarket(markets=markets, limit=limit)
        elif mode == "intraday":
            run_intraday(markets=markets)
        elif mode == "postmarket":
            run_postmarket(markets=markets)
    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断[/yellow]")
    except Exception as e:
        console.print(f"\n[red]流程失败: {e}[/red]")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
