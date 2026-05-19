#!/usr/bin/env python3
"""
MarketRadar 持续模拟运行

A股交易时段(9:30-15:00)每30分钟执行盘中扫描，
美股交易时段(21:30-04:00)每10分钟执行盘中扫描，
港股交易时段(9:30-16:00)每30分钟执行盘中扫描，
每4小时执行一次盘后全量扫描（仅在所有市场闭市时）。
持仓价格每60秒更新一次，触发止损止盈。
按 Ctrl+C 停止。

启动：
  python run_continuous_simulation.py
"""
import sys
import time
import signal
import os
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich import box

from core.schemas import Market, PriorityLevel
from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine
from m12_opportunity_catcher.anomaly_detector import AnomalyDetector
from m12_opportunity_catcher.stock_universe import get_stock_universe
from m9_paper_trader.baostock_feed import BaostockFeed
from m9_paper_trader.eastmoney_feed import EastMoneyFeed
from m9_paper_trader.price_feed import YFinanceFeed
from m9_paper_trader.futu_feed import FutuFeed
from m9_paper_trader.paper_trader import PaperTrader
from m9_paper_trader.price_snapshot_logger import PriceSnapshotLogger

console = Console()

RUNNING = True
A_SHARE_FEED = None

_trader = PaperTrader()
_price_logger = PriceSnapshotLogger()


def _signal_handler(sig, frame):
    global RUNNING
    console.print("\n[yellow]收到停止信号，正在退出...[/yellow]")
    RUNNING = False


def detect_a_share_feed():
    """自动检测最优A股数据源：Futu > EastMoney > Baostock"""
    try:
        futu = FutuFeed()
        if futu._connected:
            snap = futu.get_price("000001.SZ")
            if snap and snap.price > 0:
                console.print("[bold green]++ Futu OpenD connected, using FutuFeed (realtime)[/bold green]")
                return FutuFeed
        futu.close()
    except Exception:
        pass

    try:
        ef = EastMoneyFeed()
        snap = ef.get_price("000001.SZ")
        if snap and snap.price > 0:
            console.print("[bold green]++ EastMoney OK, using EastMoneyFeed (3-5s delay)[/bold green]")
            return EastMoneyFeed
    except Exception:
        pass

    console.print("[bold yellow]-- Back to Baostock daily (T+1 data)[/bold yellow]")
    return BaostockFeed


signal.signal(signal.SIGINT, _signal_handler)


# Removed duplicate function - using the one at line 267 with auto-open logic


def _get_feed_configs(a_share_feed_cls=None, is_a_share_trading_fn=None, is_us_trading_fn=None):
    """获取数据源配置（Futu优先, 降级备选）。支持智能市场选择。"""
    if a_share_feed_cls is None:
        a_share_feed_cls = detect_a_share_feed()

    # Smart market selection based on trading hours
    now_h = datetime.now().hour
    is_a_share_hours = is_a_share_trading_fn() if is_a_share_trading_fn else (9 <= now_h < 15)
    is_us_hours = is_us_trading_fn() if is_us_trading_fn else (21 <= now_h or now_h < 4)

    try:
        from m9_paper_trader.futu_feed import FutuFeed
        futu_test = FutuFeed()
        if futu_test._connected:
            configs = []
            if is_a_share_hours:
                configs.append((Market.A_SHARE, FutuFeed))
                configs.append((Market.HK, FutuFeed))
            if is_us_hours:
                configs.append((Market.US, FutuFeed))

            # If no market is trading, scan all (off-hours scan)
            if not configs:
                configs = [
                    (Market.A_SHARE, FutuFeed),
                    (Market.HK, FutuFeed),
                    (Market.US, FutuFeed),
                ]
            futu_test.close()
            return configs, FutuFeed
        futu_test.close()
    except Exception:
        pass

    configs = []
    if is_a_share_hours:
        configs.append((Market.A_SHARE, a_share_feed_cls))
        configs.append((Market.HK, YFinanceFeed))
    if is_us_hours:
        configs.append((Market.US, YFinanceFeed))

    # If no market is trading, scan all
    if not configs:
        configs = [
            (Market.A_SHARE, a_share_feed_cls),
            (Market.HK, YFinanceFeed),
            (Market.US, YFinanceFeed),
        ]
    return configs, None


def run_daily_scan(a_share_feed_cls=None, max_anomalies=5):
    """盘后全量扫描（仅在所有市场闭市时执行）

    Args:
        max_anomalies: 每轮每市场最多处理的异动数量，0=不限制
    """
    if a_share_feed_cls is None:
        a_share_feed_cls = BaostockFeed

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"\n[bold green]═══ 盘后全量扫描 @ {now} ═══[/bold green]")

    markets_configs, feed_cls_for_open = _get_feed_configs(a_share_feed_cls)

    all_results = []
    total = 0

    # 并行扫描多个市场
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for market, feed_cls in markets_configs:
            future = executor.submit(_scan_single_market, market, feed_cls, is_intraday=False, max_anomalies=max_anomalies)
            futures[future] = market

        for future in as_completed(futures):
            market = futures[future]
            try:
                results = future.result()
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
                    all_results.extend(results)
                else:
                    console.print(f"  [dim]{market.value}: 无异动[/dim]")
            except Exception as e:
                console.print(f"  [yellow]⚠ {market.value} 扫描失败: {e}[/yellow]")

    console.print(f"\n  [bold]盘后总计: {total} 个补牢机会[/bold]")

    if all_results:
        console.print("\n[bold cyan]═══ M12→M4→M9 自动开仓 ═══[/bold cyan]")
        open_results = _auto_open_from_opportunities(all_results, feed_cls_for_open)
        _print_open_results(open_results)

    _save_results(total)

    # Generate daily decision report
    try:
        from pipeline.decision_log import DecisionLog
        dl = DecisionLog()
        report = dl.generate_daily_report()
        summary = report.get("summary", {})
        console.print(f"\n  [dim]决策报告: 异动{summary.get('total_anomalies',0)} "
                      f"无因放弃{summary.get('skipped_no_cause',0)} "
                      f"M3否决{summary.get('skipped_m3_no_opportunity',0)} "
                      f"趋势晚放弃{summary.get('skipped_trend_late',0)} "
                      f"开仓{summary.get('opened_positions',0)}[/dim]")
    except Exception as e:
        console.print(f"  [yellow]决策报告生成失败: {e}[/yellow]")

    return total


def _scan_single_market(market, feed_cls, is_intraday=True, max_anomalies=0):
    """扫描单个市场（用于并行执行）

    Args:
        max_anomalies: 每轮最多处理的异动数量，0=不限制（控制LLM成本）
    """
    try:
        console.print(f"  [bold]扫描 {market.value}...[/bold]")
        # v2 阈值: 低阈值 + N日累计异动（经回测验证，TPR 14.4%→35.3%）
        detector_kwargs = dict(
            sigma_threshold=1.5,
            atr_threshold=1.5,
            volume_threshold=1.2,
            n_day_windows=(3, 5),
        )

        detector = AnomalyDetector(**detector_kwargs)
        engine = OpportunityCatcherEngine(anomaly_detector=detector)
        pf = feed_cls()

        if is_intraday:
            # 盘中扫描：记录价格快照
            stock_universe = get_stock_universe()
            stock_list = stock_universe.get_stock_list(market)
            _record_price_snapshots(market, stock_list, pf)
            results = engine.run_intraday_scan(market=market, price_feed=pf, max_anomalies=max_anomalies)
        else:
            # 盘后扫描
            results = engine.run_daily_scan(market=market, price_feed=pf, max_anomalies=max_anomalies)

        return results
    except Exception as e:
        console.print(f"  [yellow]⚠ {market.value} 扫描失败: {e}[/yellow]")
        return []


def run_intraday_scan(markets_to_scan=None, a_share_feed_cls=None, max_anomalies=3):
    """盘中扫描（支持指定市场列表，并行执行）

    Args:
        max_anomalies: 每轮每市场最多处理的异动数量，0=不限制（控制LLM成本）
    """
    if a_share_feed_cls is None:
        a_share_feed_cls = detect_a_share_feed()

    # 如果未指定市场，根据交易时段自动选择
    if markets_to_scan is None:
        now_h = datetime.now().hour
        markets_to_scan = []
        if 9 <= now_h < 15:  # A股时段
            markets_to_scan.append(Market.A_SHARE)
        if 9 <= now_h < 16:  # 港股时段
            markets_to_scan.append(Market.HK)
        if 21 <= now_h or now_h < 4:  # 美股时段
            markets_to_scan.append(Market.US)

    if not markets_to_scan:
        return 0

    # 获取数据源配置
    feed_map = {
        Market.A_SHARE: a_share_feed_cls,
        Market.HK: FutuFeed,
        Market.US: FutuFeed,
    }

    # 尝试使用Futu统一数据源
    try:
        futu_test = FutuFeed()
        if futu_test._connected:
            feed_map = {m: FutuFeed for m in markets_to_scan}
            feed_cls_for_open = FutuFeed
        futu_test.close()
    except:
        feed_cls_for_open = a_share_feed_cls

    all_results = []
    total = 0

    # 并行扫描多个市场
    with ThreadPoolExecutor(max_workers=len(markets_to_scan)) as executor:
        futures = {}
        for market in markets_to_scan:
            feed_cls = feed_map.get(market, a_share_feed_cls)
            future = executor.submit(_scan_single_market, market, feed_cls, is_intraday=True, max_anomalies=max_anomalies)
            futures[future] = market

        for future in as_completed(futures):
            market = futures[future]
            try:
                results = future.result()
                if results:
                    console.print(f"  [green]✓ {market.value}: {len(results)} 个补牢机会[/green]")
                    for r in results[:3]:
                        a = r.anomaly
                        console.print(
                            f"    {a.instrument} {a.price_change_pct:+.1f}% "
                            f"({a.anomaly_type}) [{r.trend.stage.value}]"
                        )
                    total += len(results)
                    all_results.extend(results)
                else:
                    console.print(f"  [dim]{market.value}: 无异动[/dim]")
            except Exception as e:
                console.print(f"  [yellow]⚠ {market.value} 扫描失败: {e}[/yellow]")

    console.print(f"\n  [bold]盘中总计: {total} 个补牢机会[/bold]")

    if all_results:
        console.print("\n[bold cyan]═══ M12→M4→M9 自动开仓 ═══[/bold cyan]")
        open_results = _auto_open_from_opportunities(all_results, feed_cls_for_open, max_positions=1)
        _print_open_results(open_results)

    return total


def _record_price_snapshots(market, stock_list, price_feed):
    """记录价格快照（批量获取，避免逐个查询）。"""
    try:
        from m9_paper_trader.price_snapshot_logger import get_price_snapshot_logger
        logger = get_price_snapshot_logger()

        # 限制每次扫描数量，避免API超时
        # A股: 最多500只 (5128只 -> 每10次扫描覆盖全部)
        # 美股: 最多200只 (12790只 -> 每64次扫描覆盖全部)
        max_stocks = 500 if market == Market.A_SHARE else 200

        # 轮转扫描：使用时间戳作为偏移量，确保每次扫描不同的股票
        import time
        offset = int(time.time() / 300) % (len(stock_list) // max_stocks + 1)  # 每5分钟轮转
        start_idx = offset * max_stocks
        end_idx = min(start_idx + max_stocks, len(stock_list))
        stock_batch = stock_list[start_idx:end_idx]

        console.print(f"  [dim]扫描 {market.value} 第 {offset+1} 批: {start_idx}-{end_idx}/{len(stock_list)}[/dim]")

        # 批量获取价格数据
        snapshots = []
        for symbol in stock_batch:
            try:
                bars = price_feed.get_bars(symbol, period="1d", count=1)
                if bars and len(bars) > 0:
                    bar = bars[-1]
                    snapshots.append({
                        'symbol': symbol,
                        'price': bar.close,
                        'change_pct': ((bar.close - bar.open) / bar.open * 100) if bar.open > 0 else 0,
                        'volume': bar.volume
                    })
            except:
                continue

        if snapshots:
            logger.log_batch(market.value, snapshots)
            console.print(f"  [dim]已记录 {len(snapshots)} 个标的价格快照[/dim]")
    except Exception as e:
        console.print(f"  [dim]价格快照记录失败: {e}[/dim]")


def run_signal_pipeline(batch_id: str = None) -> dict:
    """
    信号管道：扫描 data/incoming/ 新文件 → M1解码 → M2存储 → M3判断 → 返回机会列表

    Args:
        batch_id: 批次ID（可选）

    Returns:
        {
            "processed_files": int,
            "total_opportunities": int,
            "opportunities": List[OpportunityObject],
        }
    """
    from m1_decoder.decoder import SignalDecoder
    from m2_storage.signal_store import SignalStore
    from m3_judgment.judgment_engine import JudgmentEngine
    from core.llm_client import LLMClient
    from core.schemas import SourceType
    from datetime import timedelta

    incoming_dir = Path("data/incoming")
    processed_dir = Path("data/processed")
    incoming_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(incoming_dir.glob("*.txt"))
    if not files:
        return {"processed_files": 0, "total_opportunities": 0, "opportunities": []}

    llm_client = LLMClient()
    decoder = SignalDecoder(llm_client=llm_client)
    store = SignalStore()
    engine = JudgmentEngine(llm_client=llm_client)

    all_opportunities = []
    processed_count = 0

    # 限制每次最多处理5个文件
    for f in files[:5]:
        try:
            raw_text = f.read_text(encoding="utf-8")
            batch_id = batch_id or f"signal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # M1 解码
            signals = decoder.decode(
                raw_text=raw_text,
                source_ref=f.name,
                source_type=SourceType("news"),
                batch_id=batch_id,
            )

            if not signals:
                f.rename(processed_dir / f.name)
                processed_count += 1
                continue

            # M2 存储
            store.save(signals)

            # M3 判断（查询90天历史信号）
            hist = store.get_by_time_range(
                start=datetime.now() - timedelta(days=90),
                end=datetime.now(),
                markets=[Market.A_SHARE, Market.HK, Market.US],
                min_intensity=5,
            )
            cur_ids = {s.signal_id for s in signals}
            hist = [s for s in hist if s.signal_id not in cur_ids]

            opportunities = engine.judge(
                signals=signals,
                historical_signals=hist or None,
                batch_id=batch_id
            )

            # 记录来源信息（通过opportunity_id后缀标记）
            for opp in opportunities:
                # 在opportunity_id中添加来源标记
                if not opp.opportunity_id.endswith("_signal"):
                    opp.opportunity_id = f"{opp.opportunity_id}_signal"

            # 打印每个机会的详情，便于判断是否是不同的交易选择
            for opp in opportunities:
                instruments = ", ".join(opp.target_instruments[:3])
                console.print(f"      [{opp.priority_level}] {opp.opportunity_title[:60]} | {opp.trade_direction} | {instruments}")

            all_opportunities.extend(opportunities)

            # 移动到已处理
            f.rename(processed_dir / f.name)
            processed_count += 1

            console.print(f"  [green]✓ {f.name}: {len(signals)}信号 → {len(opportunities)}机会[/green]")

        except Exception as e:
            console.print(f"  [yellow]⚠ 处理失败 {f.name}: {e}[/yellow]")
            continue

    return {
        "processed_files": processed_count,
        "total_opportunities": len(all_opportunities),
        "opportunities": all_opportunities
    }


def _process_signal_pipeline(branch_manager):
    """处理信号管道并通过BranchManager评估机会。"""
    try:
        result = run_signal_pipeline()
        if result["processed_files"] == 0:
            return

        console.print(f"\n[bold cyan]信号管道: {result['processed_files']}文件 → {result['total_opportunities']}机会[/bold cyan]")

        # 通过BranchManager处理每个机会
        for opp in result["opportunities"]:
            try:
                branch_result = branch_manager.process_opportunity(opp, source="signal_pipeline")
                if branch_result["selected_branch"]:
                    # 自动开仓
                    _open_single_opportunity(
                        opportunity=branch_result["opportunity"],
                        branch_id=branch_result["selected_branch"],
                        branch_manager=branch_manager
                    )
            except Exception as e:
                console.print(f"  [yellow]⚠ 处理机会失败 {opp.instrument}: {e}[/yellow]")

    except Exception as e:
        console.print(f"  [red]信号管道处理失败: {e}[/red]")


def _open_single_opportunity(opportunity, branch_id: str, branch_manager):
    """为单个机会开仓并记录到分支。"""
    try:
        from m4_action.action_plan import ActionPlan
        from core.schemas import Direction

        # 从OpportunityObject提取信息
        # 注意：OpportunityObject是M3的输出，需要转换为M4的输入
        instrument = opportunity.target_instruments[0] if opportunity.target_instruments else None
        if not instrument:
            console.print(f"  [yellow]⚠ 机会无具体标的，跳过[/yellow]")
            return

        # 创建ActionPlan
        plan = ActionPlan(
            instrument=instrument,
            direction=opportunity.trade_direction,
            entry_price=0.0,  # 将由trader获取实时价格
            stop_loss_price=0.0,  # 将由M4计算
            take_profit_price=0.0,  # 将由M4计算
            priority=opportunity.priority_level,
            reasoning=opportunity.opportunity_thesis,
            metadata={
                "branch_id": branch_id,
                "opportunity_id": opportunity.opportunity_id,
                "source": "signal_pipeline" if "_signal" in opportunity.opportunity_id else "m12_anomaly"
            }
        )

        # 执行开仓
        position = _trader.open_position(plan)
        if position:
            # 记录到分支
            branch_manager.branches[branch_id].position_ids.append(position.position_id)
            console.print(f"  [green]✓ 开仓成功: {instrument} ({branch_id})[/green]")
        else:
            console.print(f"  [yellow]⚠ 开仓被拒绝: {instrument}[/yellow]")

    except Exception as e:
        console.print(f"  [red]开仓失败: {e}[/red]")


def _auto_open_from_opportunities(results, feed_cls, max_positions=3):
    """M12 RetroOpportunity → M4 ActionPlan → M9 PaperTrader 自动开仓。"""
    try:
        from pipeline.opportunity_to_position import opportunities_to_positions
        return opportunities_to_positions(
            opportunities=results,
            feed_cls=feed_cls,
            max_positions=max_positions,
            min_priority=PriorityLevel.RESEARCH,
            trader=_trader,
        )
    except Exception as e:
        console.print(f"  [red]自动开仓失败: {e}[/red]")
        import traceback
        traceback.print_exc()
        return []


def _print_open_results(open_results):
    """打印开仓结果摘要。"""
    if not open_results:
        console.print("  [dim]无符合条件的机会开仓[/dim]")
        return

    from rich.table import Table
    table = Table(title="模拟开仓结果", box=box.SIMPLE)
    table.add_column("标的", style="cyan")
    table.add_column("方向", style="green")
    table.add_column("入场价", style="white")
    table.add_column("止损价", style="red")
    table.add_column("止盈价", style="green")
    table.add_column("状态", style="yellow")

    for r in open_results:
        status = r.get("status", "unknown")
        status_style = "green" if status == "opened" else "red" if status == "rejected" else "yellow"
        table.add_row(
            r.get("instrument", "?"),
            r.get("direction", "?"),
            f"{r.get('entry_price', 0):.2f}",
            f"{r.get('stop_loss_price', 0):.2f}",
            f"{r.get('take_profit_price', 0):.2f}" if r.get('take_profit_price') else "-",
            f"[{status_style}]{status}[/{status_style}]",
        )
    console.print(table)


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
    console.print("[bold green]╔══════════════════════════════════════════════════╗[/bold green]")
    console.print("[bold green]║  MarketRadar 持续模拟运行                        ║[/bold green]")
    console.print("[bold green]║  A股: 9:30-15:00 | 港股: 9:30-16:00              ║[/bold green]")
    console.print("[bold green]║  美股: 21:30-04:00 | 并行扫描 | 智能调度          ║[/bold green]")
    console.print("[bold green]║  按 Ctrl+C 停止                                   ║[/bold green]")
    console.print("[bold green]╚══════════════════════════════════════════════════╝[/bold green]")

    console.print("[bold]检测数据源...[/bold]")
    a_share_feed_cls = detect_a_share_feed()

    # 初始化多分支A/B测试管理器
    from pipeline.branch_manager import BranchManager
    branch_manager = BranchManager()
    console.print(f"[bold cyan]多分支测试已启用: {len(branch_manager.branches)}个分支[/bold cyan]")

    # 交易时段定义
    a_share_trading_hours = ((9, 30), (15, 0))
    hk_trading_hours = ((9, 30), (16, 0))
    us_trading_hours = ((21, 30), (4, 0))

    def _is_in_range(now_h: int, now_m: int, start: tuple, end: tuple) -> bool:
        start_min = start[0] * 60 + start[1]
        end_min = end[0] * 60 + end[1]
        now_min = now_h * 60 + now_m
        if start_min <= end_min:
            return start_min <= now_min <= end_min
        else:
            return now_min >= start_min or now_min <= end_min

    def is_a_share_trading():
        now_h, now_m = datetime.now().hour, datetime.now().minute
        return _is_in_range(now_h, now_m, a_share_trading_hours[0], a_share_trading_hours[1])

    def is_hk_trading():
        now_h, now_m = datetime.now().hour, datetime.now().minute
        return _is_in_range(now_h, now_m, hk_trading_hours[0], hk_trading_hours[1])

    def is_us_trading():
        now_h, now_m = datetime.now().hour, datetime.now().minute
        return _is_in_range(now_h, now_m, us_trading_hours[0], us_trading_hours[1])

    def is_any_market_trading():
        return is_a_share_trading() or is_hk_trading() or is_us_trading()

    def is_weekend():
        return datetime.now().weekday() >= 5

    # 首次启动：仅在闭市时执行盘后扫描
    if not is_any_market_trading():
        console.print("\n[bold]首次启动：执行盘后全量扫描...[/bold]")
        run_daily_scan(a_share_feed_cls=a_share_feed_cls)
    else:
        console.print("\n[bold]首次启动：市场开盘中，跳过盘后扫描[/bold]")

    # 扫描间隔
    a_share_intraday_interval = 10 * 60  # A股10分钟
    hk_intraday_interval = 10 * 60       # 港股10分钟
    us_intraday_interval = 10 * 60       # 美股10分钟
    daily_interval = 4 * 60 * 60         # 盘后4小时
    price_update_interval = 60           # 价格更新60秒

    last_a_share_scan = 0.0
    last_hk_scan = 0.0
    last_us_scan = 0.0
    last_daily = time.time()
    last_price_update = 0.0
    cycle = 0

    def update_open_positions():
        open_positions = _trader.list_open()
        if not open_positions:
            return
        try:
            feed_cls_for_update = _get_feed_for_positions(open_positions)
            if feed_cls_for_update is None:
                return
            feed = feed_cls_for_update() if callable(feed_cls_for_update) else feed_cls_for_update
            result = _trader.update_all_prices(feed)
            if result.get("updated", 0) > 0:
                closed = result.get("closed", [])
                if closed:
                    for pid in closed:
                        console.print(f"  [bold red]⚡ 止损/止盈触发: {pid}[/bold red]")
                now_str = datetime.now().strftime("%H:%M:%S")
                console.print(
                    f"  [dim]{now_str} 价格更新: {result['updated']}个持仓"
                    f"{f' | 平仓{len(closed)}个' if closed else ''}[/dim]"
                )
        except Exception as e:
            console.print(f"  [yellow]价格更新失败: {e}[/yellow]")

    def _get_feed_for_positions(positions):
        instruments = {p.instrument for p in positions}
        has_us = any(i.endswith(".US") for i in instruments)
        has_hk = any(i.endswith(".HK") for i in instruments)
        has_a = any(i.endswith((".SH", ".SZ")) for i in instruments)

        try:
            from m9_paper_trader.futu_feed import FutuFeed
            futu_test = FutuFeed()
            if futu_test._connected:
                futu_test.close()
                return FutuFeed
            futu_test.close()
        except Exception:
            pass

        if has_us or has_hk:
            return YFinanceFeed
        return a_share_feed_cls

    console.print("[bold green]持续运行中... (Ctrl+C 停止)[/bold green]")

    # 信号管道处理间隔（每5分钟检查一次incoming目录）
    signal_pipeline_interval = 5 * 60
    last_signal_pipeline = 0.0

    while RUNNING:
        time.sleep(10)
        now = time.time()
        now_dt = datetime.now()

        # 信号管道处理：定期检查incoming目录
        if now - last_signal_pipeline >= signal_pipeline_interval:
            _process_signal_pipeline(branch_manager)
            last_signal_pipeline = now

        # 盘后扫描：仅在所有市场闭市时执行
        if now - last_daily >= daily_interval and not is_any_market_trading():
            cycle += 1
            console.print(f"\n[dim]--- 第 {cycle} 轮盘后扫描（所有市场闭市）---[/dim]")
            run_daily_scan(a_share_feed_cls=a_share_feed_cls)
            last_daily = now
            continue

        if not is_weekend():
            # A股盘中扫描
            if is_a_share_trading() and now - last_a_share_scan >= a_share_intraday_interval:
                cycle += 1
                console.print(f"\n[dim]--- 第 {cycle} 轮A股盘中扫描 (10min) ---[/dim]")
                run_intraday_scan(markets_to_scan=[Market.A_SHARE], a_share_feed_cls=a_share_feed_cls)
                last_a_share_scan = now

            # 港股盘中扫描
            if is_hk_trading() and now - last_hk_scan >= hk_intraday_interval:
                cycle += 1
                console.print(f"\n[dim]--- 第 {cycle} 轮港股盘中扫描 (10min) ---[/dim]")
                run_intraday_scan(markets_to_scan=[Market.HK], a_share_feed_cls=a_share_feed_cls)
                last_hk_scan = now

            # 美股盘中扫描
            if is_us_trading() and now - last_us_scan >= us_intraday_interval:
                cycle += 1
                console.print(f"\n[dim]--- 第 {cycle} 轮美股盘中扫描 (10min) ---[/dim]")
                run_intraday_scan(markets_to_scan=[Market.US], a_share_feed_cls=a_share_feed_cls)
                last_us_scan = now

        # 价格更新
        if now - last_price_update >= price_update_interval:
            update_open_positions()
            last_price_update = now

    console.print("\n[yellow]模拟运行已停止[/yellow]")


if __name__ == "__main__":
    main()