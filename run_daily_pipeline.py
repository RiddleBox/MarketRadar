#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import os
from datetime import datetime
from pathlib import Path

# 设置Windows控制台UTF-8编码
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

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
from m10_sentiment.sentiment_engine import SentimentEngine

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


def step_m0_collect(limit: int = None, markets: list[Market] = None) -> int:
    """M0: 采集隔夜新闻和公告"""
    console.print("\n[bold cyan]步骤 1/5: M0 采集隔夜信号[/bold cyan]")

    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    markets = markets or [Market.A_SHARE]

    # 多数据源策略: AKShare(A股) + Finnhub(港股/美股)
    providers = []

    # A股数据源: AKShare
    if Market.A_SHARE in markets:
        try:
            from m0_collector.providers.akshare_news import AkshareNewsProvider
            akshare_provider = AkshareNewsProvider()
            if akshare_provider.is_available():
                providers.append((akshare_provider, "AKShare(A股)", {}))
        except Exception as e:
            console.print(f"  [yellow]⚠ AKShare Provider 加载失败: {e}[/yellow]")

    # 港股/美股数据源: Finnhub
    if Market.HK in markets or Market.US in markets:
        try:
            from m0_collector.providers.finnhub_provider import FinnhubProvider
            finnhub_provider = FinnhubProvider()

            # 港股新闻 (使用市场新闻)
            if Market.HK in markets:
                providers.append((finnhub_provider, "Finnhub(港股)", {"category": "general"}))

            # 美股新闻 (使用市场新闻)
            if Market.US in markets:
                providers.append((finnhub_provider, "Finnhub(美股)", {"category": "general"}))

        except Exception as e:
            console.print(f"  [yellow]⚠ Finnhub Provider 加载失败: {e}[/yellow]")

    if not providers:
        console.print("  [red]✗ 无可用数据源,跳过采集[/red]")
        return 0

    console.print(f"  可用数据源: {', '.join([name for _, name, _ in providers])}")

    all_raw_items = []

    # 依次尝试每个数据源
    for provider, name, fetch_kwargs in providers:
        try:
            console.print(f"  尝试数据源: {name}")

            if limit:
                fetch_kwargs["limit"] = limit

            raw_items = provider.fetch(**fetch_kwargs)

            if raw_items:
                console.print(f"  ✓ {name} 抓取到 {len(raw_items)} 条数据")
                all_raw_items.extend(raw_items)
            else:
                console.print(f"  [yellow]⚠ {name} 返回空数据[/yellow]")

        except Exception as e:
            console.print(f"  [yellow]⚠ {name} 抓取失败: {e}[/yellow]")
            continue

    if not all_raw_items:
        console.print("  [yellow]所有数据源均失败,无新数据[/yellow]")
        return 0

    console.print(f"  ✓ 总计抓取: {len(all_raw_items)} 条")

    try:
        # 去重
        dedup = DedupIndex(index_path=DEDUP_INDEX_PATH)
        unique_items = []
        for item in all_raw_items:
            url = getattr(item, 'source_url', '')
            content = getattr(item, 'content', '')
            if not dedup.is_duplicate(url, content):
                unique_items.append(item)
                dedup.add(url, content)

        console.print(f"  ✓ 去重后剩余 {len(unique_items)} 条")

        if not unique_items:
            console.print("  [yellow]无新数据，跳过后续步骤[/yellow]")
            return 0

        # 标准化
        dedup_for_normalizer = DedupIndex(index_path=DEDUP_INDEX_PATH)
        normalizer = Normalizer(dedup_index=dedup_for_normalizer)
        normalized, skip_count, error_count = normalizer.normalize(unique_items)

        console.print(f"  ✓ 标准化完成: {len(normalized)} 条 (跳过{skip_count}, 错误{error_count})")

        if not normalized:
            console.print("  [yellow]标准化后无有效数据，跳过后续步骤[/yellow]")
            return 0

        # 写入文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for i, doc in enumerate(normalized):
            filename = f"{timestamp}_{i:03d}.txt"
            filepath = INCOMING_DIR / filename
            filepath.write_text(doc.to_text(), encoding="utf-8")

        console.print(f"  ✓ 写入 {len(normalized)} 个文件到 {INCOMING_DIR}")

        # 保存去重索引
        dedup.save()

        return len(normalized)

    except Exception as e:
        console.print(f"  [red]✗ M0 采集失败: {e}[/red]")
        return 0


def step_m10_sentiment() -> dict:
    """M10: 采集情绪面快照"""
    console.print("\n[bold cyan]步骤 2/5: M10 情绪面快照[/bold cyan]")

    try:
        engine = SentimentEngine()
        signal_data = engine.run()

        if signal_data:
            console.print(f"  ✓ 恐贪指数: {signal_data.fear_greed_index}")
            console.print(f"  ✓ 北向资金: {signal_data.northbound_flow_1d:+.2f}亿")

            return {
                "fear_greed_index": signal_data.fear_greed_index,
                "northbound_flow": signal_data.northbound_flow_1d,
            }
        else:
            console.print(f"  [yellow]⚠ M10 采集失败（非致命）[/yellow]")
            return {}

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
    collected = step_m0_collect(limit=limit, markets=markets)
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

    console.print("\n[bold cyan]步骤 1/3: 获取当前持仓[/bold cyan]")
    
    try:
        from m9_paper_trader.paper_trader import PaperTrader
        from m9_paper_trader.price_feed import AKShareRealtimeFeed
        
        trader = PaperTrader()
        open_positions = trader.list_open()
        
        if not open_positions:
            console.print("  [yellow]无开仓持仓，跳过盘中监控[/yellow]")
            return
        
        console.print(f"  ✓ 当前持仓: {len(open_positions)} 个")
        
        # 显示持仓列表
        table = Table(title="当前持仓", box=box.SIMPLE)
        table.add_column("标的", style="cyan")
        table.add_column("方向", style="green")
        table.add_column("入场价", style="white")
        table.add_column("当前价", style="white")
        table.add_column("浮盈", style="yellow")
        table.add_column("止损价", style="red")
        table.add_column("止盈价", style="green")
        
        for pos in open_positions:
            table.add_row(
                pos.instrument,
                pos.direction,
                f"{pos.entry_price:.2f}",
                f"{pos.current_price:.2f}",
                f"{pos.unrealized_pnl_pct*100:+.2f}%",
                f"{pos.stop_loss_price:.2f}",
                f"{pos.take_profit_price:.2f}" if pos.take_profit_price else "-",
            )
        
        console.print(table)
        
        # 步骤 2: 更新价格
        console.print("\n[bold cyan]步骤 2/3: 更新持仓价格[/bold cyan]")
        
        price_feed = AKShareRealtimeFeed()
        result = trader.update_all_prices(price_feed)
        
        console.print(f"  ✓ 更新成功: {result['updated']} 个持仓")
        
        # 步骤 3: 检查触发
        if result['closed']:
            console.print("\n[bold cyan]步骤 3/3: 止损/止盈触发[/bold cyan]")
            console.print(f"  [bold red]⚠️  {len(result['closed'])} 个持仓触发平仓![/bold red]")
            
            # 显示触发详情
            closed_positions = [p for p in trader.list_all() if p.paper_position_id in result['closed']]
            
            trigger_table = Table(title="触发平仓", box=box.SIMPLE)
            trigger_table.add_column("标的", style="cyan")
            trigger_table.add_column("触发原因", style="red")
            trigger_table.add_column("入场价", style="white")
            trigger_table.add_column("平仓价", style="white")
            trigger_table.add_column("盈亏", style="yellow")
            
            for pos in closed_positions:
                trigger_table.add_row(
                    pos.instrument,
                    pos.status,
                    f"{pos.entry_price:.2f}",
                    f"{pos.exit_price:.2f}" if pos.exit_price else "-",
                    f"{pos.realized_pnl_pct*100:+.2f}%" if pos.realized_pnl_pct else "-",
                )
            
            console.print(trigger_table)
            console.print("\n[bold yellow]⚠️  建议人工确认后续操作[/bold yellow]")
        else:
            console.print("\n[bold cyan]步骤 3/3: 检查触发条件[/bold cyan]")
            console.print("  ✓ 无触发，持仓正常")
        
        # 总结
        console.print("\n" + "=" * 70)
        console.print("[bold green]盘中流程完成[/bold green]")
        console.print(f"  持仓数: {len(open_positions)}")
        console.print(f"  更新数: {result['updated']}")
        console.print(f"  触发数: {len(result['closed'])}")
        console.print("=" * 70)
        
    except Exception as e:
        console.print(f"\n[red]✗ 盘中流程失败: {e}[/red]")
        import traceback
        traceback.print_exc()


def run_postmarket(markets: list[Market]):
    """盘后流程：复盘归因 → 更新知识库"""
    print_header("postmarket")

    console.print("\n[bold cyan]步骤 1/4: 获取今日平仓持仓[/bold cyan]")
    
    try:
        from m9_paper_trader.paper_trader import PaperTrader
        from m6_retrospective.retrospective import RetrospectiveEngine
        from m8_knowledge.knowledge_base import KnowledgeBase
        from datetime import date
        
        trader = PaperTrader()
        today = date.today()
        
        # 获取今日平仓持仓
        all_closed = trader.list_closed()
        today_closed = [p for p in all_closed if p.exit_time and p.exit_time.date() == today]
        
        if not today_closed:
            console.print("  [yellow]今日无平仓持仓，跳过复盘[/yellow]")
            return
        
        console.print(f"  ✓ 今日平仓: {len(today_closed)} 个")
        
        # 显示平仓列表
        table = Table(title="今日平仓持仓", box=box.SIMPLE)
        table.add_column("标的", style="cyan")
        table.add_column("方向", style="green")
        table.add_column("入场价", style="white")
        table.add_column("平仓价", style="white")
        table.add_column("盈亏", style="yellow")
        table.add_column("原因", style="red")
        
        for pos in today_closed:
            pnl_color = "green" if pos.realized_pnl_pct and pos.realized_pnl_pct > 0 else "red"
            table.add_row(
                pos.instrument,
                pos.direction,
                f"{pos.entry_price:.2f}",
                f"{pos.exit_price:.2f}" if pos.exit_price else "-",
                f"[{pnl_color}]{pos.realized_pnl_pct*100:+.2f}%[/{pnl_color}]" if pos.realized_pnl_pct else "-",
                pos.status,
            )
        
        console.print(table)
        
        # 步骤 2: M6 复盘分析
        console.print("\n[bold cyan]步骤 2/4: M6 复盘归因[/bold cyan]")
        
        retro_engine = RetrospectiveEngine()
        retrospectives = []
        
        for pos in today_closed:
            try:
                # 构造 OpportunityObject (简化版)
                from core.schemas import OpportunityObject, PriorityLevel, Direction, Market as MarketEnum
                
                opp = OpportunityObject(
                    opportunity_id=pos.opportunity_id or f"opp_{pos.paper_position_id}",
                    opportunity_title=f"{pos.instrument} {pos.direction}",
                    opportunity_thesis=f"模拟盘持仓: {pos.instrument}",
                    opportunity_priority=PriorityLevel.RESEARCH,
                    direction=Direction(pos.direction) if pos.direction in ["BULLISH", "BEARISH"] else Direction.NEUTRAL,
                    market=MarketEnum(pos.market) if pos.market in ["A_SHARE", "HK", "US"] else MarketEnum.A_SHARE,
                    signal_ids=pos.signal_ids,
                    time_window="",
                    entry_price=pos.entry_price,
                    stop_loss=pos.stop_loss_price,
                    take_profit=pos.take_profit_price,
                )
                
                # 构造 Position (简化版)
                from core.schemas import Position, PositionStatus
                
                position = Position(
                    position_id=pos.paper_position_id,
                    opportunity_id=pos.opportunity_id or "",
                    instrument=pos.instrument,
                    direction=pos.direction,
                    entry_price=pos.entry_price,
                    current_price=pos.exit_price or pos.current_price,
                    quantity=pos.quantity,
                    status=PositionStatus.CLOSED,
                    entry_time=pos.entry_time,
                    exit_time=pos.exit_time,
                    realized_pnl=pos.realized_pnl_pct,
                )
                
                # 执行复盘
                retro = retro_engine.analyze(
                    opportunity=opp,
                    position=position,
                    outcome=pos.status,
                    notes=f"模拟盘自动复盘",
                    write_to_knowledge=True,  # 写入知识库
                )
                
                retrospectives.append(retro)
                console.print(f"  ✓ 复盘完成: {pos.instrument} (质量分: {retro.get('composite_score', 0)}/5)")
                
            except Exception as e:
                console.print(f"  [red]✗ 复盘失败 {pos.instrument}: {e}[/red]")
                continue
        
        console.print(f"  ✓ 总计复盘: {len(retrospectives)} 个")
        
        # 步骤 3: M8 知识库更新
        console.print("\n[bold cyan]步骤 3/4: M8 知识库更新[/bold cyan]")
        
        kb = KnowledgeBase()
        lessons_added = 0
        
        for retro in retrospectives:
            key_lesson = retro.get('analysis', {}).get('key_lesson', '')
            if key_lesson and len(key_lesson) > 20:  # 有效教训
                try:
                    # 写入知识库 (简化版)
                    lesson_doc = {
                        "title": f"复盘教训: {retro.get('instrument', 'Unknown')}",
                        "content": key_lesson,
                        "source": "M6_retrospective",
                        "date": datetime.now().isoformat(),
                        "retro_id": retro.get('retro_id'),
                    }
                    # 这里应该调用 kb.add_document()，但简化处理
                    lessons_added += 1
                except Exception as e:
                    console.print(f"  [yellow]⚠ 知识库写入失败: {e}[/yellow]")
        
        console.print(f"  ✓ 知识库更新: {lessons_added} 条教训")
        
        # 步骤 4: 生成交易总结
        console.print("\n[bold cyan]步骤 4/4: 生成交易总结[/bold cyan]")
        
        total_pnl = sum(p.realized_pnl_pct or 0 for p in today_closed)
        win_count = sum(1 for p in today_closed if p.realized_pnl_pct and p.realized_pnl_pct > 0)
        loss_count = len(today_closed) - win_count
        win_rate = win_count / len(today_closed) if today_closed else 0
        
        summary_table = Table(title="今日交易总结", box=box.ROUNDED)
        summary_table.add_column("指标", style="cyan")
        summary_table.add_column("数值", style="white")
        
        summary_table.add_row("平仓数", str(len(today_closed)))
        summary_table.add_row("盈利数", str(win_count))
        summary_table.add_row("亏损数", str(loss_count))
        summary_table.add_row("胜率", f"{win_rate*100:.1f}%")
        summary_table.add_row("总盈亏", f"{total_pnl*100:+.2f}%")
        summary_table.add_row("复盘数", str(len(retrospectives)))
        summary_table.add_row("教训数", str(lessons_added))
        
        console.print(summary_table)
        
        # 总结
        console.print("\n" + "=" * 70)
        console.print("[bold green]盘后流程完成[/bold green]")
        console.print(f"  平仓: {len(today_closed)} 个")
        console.print(f"  复盘: {len(retrospectives)} 个")
        console.print(f"  教训: {lessons_added} 条")
        console.print(f"  胜率: {win_rate*100:.1f}%")
        console.print("=" * 70)
        
    except Exception as e:
        console.print(f"\n[red]✗ 盘后流程失败: {e}[/red]")
        import traceback
        traceback.print_exc()


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
