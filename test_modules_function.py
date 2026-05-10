"""
模块功能测试：测试关键模块的核心功能
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

print("=" * 80)
print("MarketRadar 模块功能测试")
print("=" * 80)

results = []

# 测试 M2 存储 - 查询功能
print("\n[M2 存储] 测试信号查询...")
try:
    from m2_storage.signal_store import SignalStore
    from core.schemas import Market

    store = SignalStore()

    # 查询最近7天的信号
    signals_7d = store.get_by_time_range(
        start=datetime.now() - timedelta(days=7),
        end=datetime.now()
    )

    # 查询A股市场信号
    signals_astock = store.get_by_time_range(
        start=datetime.now() - timedelta(days=7),
        end=datetime.now(),
        markets=[Market.A_SHARE]
    )

    print(f"  [OK] 最近7天信号: {len(signals_7d)}")
    print(f"  [OK] A股信号: {len(signals_astock)}")
    results.append(("M2_storage_query", "OK", f"7天:{len(signals_7d)}, A股:{len(signals_astock)}"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M2_storage_query", "FAIL", str(e)))

# 测试 M9 模拟交易 - 持仓管理
print("\n[M9 模拟交易] 测试持仓管理...")
try:
    from m9_paper_trader.paper_trader import PaperTrader

    trader = PaperTrader()

    # 获取持仓
    open_positions = trader.list_open()
    closed_positions = trader.list_closed()

    # 计算统计
    total_pnl = sum(p.realized_pnl for p in closed_positions if p.realized_pnl)

    print(f"  [OK] 开仓数: {len(open_positions)}")
    print(f"  [OK] 已平仓数: {len(closed_positions)}")
    print(f"  [OK] 累计盈亏: {total_pnl:.2f}")

    results.append(("M9_paper_trader_positions", "OK",
                   f"开仓:{len(open_positions)}, 已平:{len(closed_positions)}, PnL:{total_pnl:.2f}"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M9_paper_trader_positions", "FAIL", str(e)))

# 测试 M7 调度器 - 任务列表
print("\n[M7 调度器] 测试任务配置...")
try:
    from m7_scheduler.scheduler import Scheduler

    scheduler = Scheduler()

    # 获取任务列表
    tasks = scheduler.list_tasks()
    enabled_tasks = [t for t in tasks if t.get('enabled', False)]

    print(f"  [OK] 总任务数: {len(tasks)}")
    print(f"  [OK] 启用任务数: {len(enabled_tasks)}")

    # 显示前5个任务
    for task in tasks[:5]:
        print(f"      - {task.get('name', 'unknown')}: {task.get('schedule', 'N/A')}")

    results.append(("M7_scheduler_tasks", "OK",
                   f"总任务:{len(tasks)}, 启用:{len(enabled_tasks)}"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M7_scheduler_tasks", "FAIL", str(e)))

# 测试 M10 情绪追踪 - 历史数据
print("\n[M10 情绪追踪] 测试情绪历史...")
try:
    from m10_sentiment.sentiment_store import SentimentStore

    store = SentimentStore()

    # 获取最近的情绪数据
    recent = store.get_recent(days=7)

    if recent:
        latest = recent[0]
        print(f"  [OK] 最近7天记录数: {len(recent)}")
        print(f"  [OK] 最新恐贪指数: {latest.fear_greed_index:.1f}")
        print(f"  [OK] 最新时间: {latest.timestamp.strftime('%Y-%m-%d %H:%M')}")

        results.append(("M10_sentiment_history", "OK",
                       f"7天记录:{len(recent)}, 最新FG:{latest.fear_greed_index:.1f}"))
    else:
        print(f"  [WARN] 无历史数据")
        results.append(("M10_sentiment_history", "WARN", "无历史数据"))

except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M10_sentiment_history", "FAIL", str(e)))

# 测试 M12 机会捕捉 - 扫描结果
print("\n[M12 机会捕捉] 测试扫描结果...")
try:
    import json

    scan_results_file = ROOT / "data" / "m12_scan_results.json"

    if scan_results_file.exists():
        with open(scan_results_file, 'r', encoding='utf-8') as f:
            scan_data = json.load(f)

        total_scans = len(scan_data.get('scans', []))
        latest_scan = scan_data.get('scans', [{}])[-1] if scan_data.get('scans') else {}

        print(f"  [OK] 总扫描次数: {total_scans}")
        if latest_scan:
            print(f"  [OK] 最新扫描: {latest_scan.get('timestamp', 'N/A')}")
            print(f"  [OK] 发现机会: {latest_scan.get('opportunities_found', 0)}")

        results.append(("M12_scan_results", "OK",
                       f"扫描次数:{total_scans}, 最新机会:{latest_scan.get('opportunities_found', 0)}"))
    else:
        print(f"  [WARN] 无扫描结果文件")
        results.append(("M12_scan_results", "WARN", "无扫描结果文件"))

except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("M12_scan_results", "FAIL", str(e)))

# 测试数据文件完整性
print("\n[数据完整性] 检查关键数据文件...")
try:
    data_files = {
        "信号数据库": ROOT / "data" / "signals" / "signal_store.db",
        "持仓数据库": ROOT / "data" / "portfolio.db",
        "情绪数据库": ROOT / "data" / "sentiment" / "sentiment_history.db",
        "调度器状态": ROOT / "data" / "scheduler_state.json",
        "股票池": ROOT / "data" / "stock_universe.json",
    }

    missing = []
    existing = []

    for name, path in data_files.items():
        if path.exists():
            size = path.stat().st_size
            print(f"  [OK] {name}: {size:,} bytes")
            existing.append(name)
        else:
            print(f"  [WARN] {name}: 不存在")
            missing.append(name)

    results.append(("data_integrity", "OK" if not missing else "WARN",
                   f"存在:{len(existing)}, 缺失:{len(missing)}"))
except Exception as e:
    print(f"  [X] 失败: {e}")
    results.append(("data_integrity", "FAIL", str(e)))

# 汇总报告
print("\n" + "=" * 80)
print("功能测试汇总")
print("=" * 80)

ok_count = sum(1 for _, status, _ in results if status == "OK")
warn_count = sum(1 for _, status, _ in results if status == "WARN")
fail_count = sum(1 for _, status, _ in results if status == "FAIL")

print(f"\n总计: {len(results)} 项测试")
print(f"  [OK] 通过: {ok_count}")
print(f"  [WARN] 警告: {warn_count}")
print(f"  [X] 失败: {fail_count}")

if fail_count > 0:
    print("\n失败测试详情:")
    for test, status, msg in results:
        if status == "FAIL":
            print(f"  - {test}: {msg}")

print("\n所有测试结果:")
for test, status, msg in results:
    if status == "OK":
        status_icon = "[OK]"
    elif status == "WARN":
        status_icon = "[WARN]"
    else:
        status_icon = "[X]"
    print(f"  {status_icon} {test:30s} {msg}")

print("\n" + "=" * 80)
print(f"测试完成 - 通过率: {ok_count}/{len(results)} ({ok_count*100//len(results) if results else 0}%)")
print("=" * 80)
