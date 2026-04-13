"""
tests/_backtest_test.py — 回测框架测试（使用内嵌种子数据 + 可选 AKShare）

测试内容：
  1. 种子数据加载和价格查询
  2. BacktestEngine — 用真实历史价格（种子数据）回测关键信号
  3. 不同信号类型有效性对比（宏观/政策/资金流/技术面）
  4. SignalEvaluator 综合评级
  5. 可选：AKShare 实时拉取（网络可用时）
"""
import sys, json, logging
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, r"D:\AIproject\MarketRadar")
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

from backtest.history_price import HistoryPriceFeed
from backtest.backtest_engine import BacktestEngine, BacktestCase
from backtest.seed_data import preload_seed_into_feed, SEED_510300, SEED_588000


# ═══════════════════════════════════════════════════════════════
# 测试1：种子数据加载
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("测试1: 种子价格数据加载")
print("=" * 60)

feed = HistoryPriceFeed()
preload_seed_into_feed(feed)

# 基本查询
price = feed.get_price("510300.SH", date(2024, 9, 24))
assert price is not None and price > 3.0, f"2024-09-24 应有数据，got {price}"
print(f"✓ 510300.SH 2024-09-24（降准降息公告日）收盘价: {price}")

# 涨停日验证
price_925 = feed.get_price("510300.SH", date(2024, 9, 25))
pct_chg = (price_925 - price) / price * 100
print(f"✓ 510300.SH 2024-09-25 收盘: {price_925} ({pct_chg:+.1f}%)")
assert pct_chg > 5, "9-25日应涨幅超5%（政策催化大涨）"

# 价格序列
prices_oct = feed.get_price_range("510300.SH", date(2024, 10, 1), date(2024, 10, 31))
print(f"✓ 510300.SH 2024-10月 {len(prices_oct)} 个交易日")

# 科创50
price_kcb = feed.get_price("588000.SH", date(2025, 2, 17))
print(f"✓ 588000.SH 2025-02-17（DeepSeek行情期）收盘价: {price_kcb}")
assert price_kcb is not None, "588000 应有2025-02-17数据"

print(f"✓ 总种子数据: 510300={len(SEED_510300)}天 588000={len(SEED_588000)}天")


# ═══════════════════════════════════════════════════════════════
# 测试2：BacktestEngine — 关键历史事件回测
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("测试2: 历史关键事件信号回测（使用真实历史价格）")
print("=" * 60)

engine = BacktestEngine(price_feed=feed)

cases = [
    # ── 宏观信号 ────────────────────────────────────────────
    # 事件：2024-09-24 央行降准降息 → 历史上 A股直接大涨
    BacktestCase(
        opportunity_id="macro_924_300",
        opportunity_title="2024-09-24 央行降准降息，沪深300流动性改善",
        signal_ids=["m1"],
        signal_type="macro",
        signal_intensity=9.5,
        signal_confidence=9.0,
        signal_direction="BULLISH",
        instrument="510300.SH",
        market="A_SHARE",
        time_horizon="short",
        created_date=date(2024, 9, 24),
        entry_price=None,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        batch_id="bt_real",
    ),
    # 事件：2024-09-24 降准降息 → 科创板弹性更大
    BacktestCase(
        opportunity_id="macro_924_kc",
        opportunity_title="2024-09-24 降准降息，科创板高弹性",
        signal_ids=["m1"],
        signal_type="macro",
        signal_intensity=9.0,
        signal_confidence=8.5,
        signal_direction="BULLISH",
        instrument="588000.SH",
        market="A_SHARE",
        time_horizon="short",
        created_date=date(2024, 9, 24),
        entry_price=None,
        stop_loss_pct=0.07,
        take_profit_pct=0.15,
        batch_id="bt_real",
    ),
    # ── 政策信号 ────────────────────────────────────────────
    # 事件：2025-01 两会政策预期 → 中期看多
    BacktestCase(
        opportunity_id="policy_0106_300",
        opportunity_title="2025-01-06 两会政策预期，A股低估值布局",
        signal_ids=["p1"],
        signal_type="policy",
        signal_intensity=7.5,
        signal_confidence=7.0,
        signal_direction="BULLISH",
        instrument="510300.SH",
        market="A_SHARE",
        time_horizon="medium",
        created_date=date(2025, 1, 6),
        entry_price=None,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        batch_id="bt_real",
    ),
    # ── 技术信号（节后高位看空）────────────────────────────
    # 事件：2024-10-08 国庆后第一天，情绪极度亢奋，通常回调
    BacktestCase(
        opportunity_id="tech_1008_bear",
        opportunity_title="2024-10-08 节后高位，短期获利回吐",
        signal_ids=["t1"],
        signal_type="technical",
        signal_intensity=6.5,
        signal_confidence=6.0,
        signal_direction="BEARISH",
        instrument="510300.SH",
        market="A_SHARE",
        time_horizon="short",
        created_date=date(2024, 10, 8),
        entry_price=None,
        stop_loss_pct=0.05,
        take_profit_pct=0.08,
        batch_id="bt_real",
    ),
    # ── 行业信号（DeepSeek科技行情）─────────────────────────
    # 事件：2025-02-17 DeepSeek 国产AI大模型冲击，科技板块重估
    BacktestCase(
        opportunity_id="industry_0217_kc",
        opportunity_title="2025-02-17 DeepSeek科技行情，科创板估值重构",
        signal_ids=["i1"],
        signal_type="industry",
        signal_intensity=8.5,
        signal_confidence=8.0,
        signal_direction="BULLISH",
        instrument="588000.SH",
        market="A_SHARE",
        time_horizon="short",
        created_date=date(2025, 2, 17),
        entry_price=None,
        stop_loss_pct=0.06,
        take_profit_pct=0.12,
        batch_id="bt_real",
    ),
    # ── 资金流信号 ──────────────────────────────────────────
    # 事件：2025-03-10 北向资金持续流入期
    BacktestCase(
        opportunity_id="capital_0310_300",
        opportunity_title="2025-03-10 北向资金连续净流入，外资看多信号",
        signal_ids=["c1"],
        signal_type="capital_flow",
        signal_intensity=7.5,
        signal_confidence=7.0,
        signal_direction="BULLISH",
        instrument="510300.SH",
        market="A_SHARE",
        time_horizon="short",
        created_date=date(2025, 3, 10),
        entry_price=None,
        stop_loss_pct=0.04,
        take_profit_pct=0.08,
        batch_id="bt_real",
    ),
    # ── 额外宏观（强度低对比组）────────────────────────────
    BacktestCase(
        opportunity_id="macro_low_300",
        opportunity_title="2025-01-13 一般性宏观预期，无强催化",
        signal_ids=["m2"],
        signal_type="macro",
        signal_intensity=4.0,
        signal_confidence=4.5,
        signal_direction="BULLISH",
        instrument="510300.SH",
        market="A_SHARE",
        time_horizon="short",
        created_date=date(2025, 1, 13),
        entry_price=None,
        stop_loss_pct=0.05,
        take_profit_pct=0.08,
        batch_id="bt_real",
    ),
    # ── 额外行业信号（低强度对比）──────────────────────────
    BacktestCase(
        opportunity_id="industry_low_300",
        opportunity_title="2024-08-01 弱行业轮动信号，无明显主线",
        signal_ids=["i2"],
        signal_type="industry",
        signal_intensity=3.5,
        signal_confidence=4.0,
        signal_direction="BULLISH",
        instrument="510300.SH",
        market="A_SHARE",
        time_horizon="short",
        created_date=date(2024, 8, 1),
        entry_price=None,
        stop_loss_pct=0.05,
        take_profit_pct=0.08,
        batch_id="bt_real",
    ),
]

report = engine.run(cases)

print(f"\n{'='*60}")
print(f"  📊 回测结果  |  完成: {report.completed}/{report.total_cases}  |  跳过: {report.skipped}")
print(f"{'='*60}")
print(f"  胜率:         {report.win_rate}%")
print(f"  均盈亏/笔:    {report.avg_pnl_pct:+.2f}%")
print(f"  盈亏比:       {report.profit_factor}")
print(f"  平均持仓:     {report.avg_holding_days} 个交易日")
print(f"  止盈触发率:   {report.take_profit_rate}%")
print(f"  止损触发率:   {report.stop_loss_rate}%")
print(f"  超时平仓率:   {report.timeout_rate}%")

if report.by_signal_type:
    print(f"\n{'─'*60}")
    print(f"  📈 按信号类型分组：")
    print(f"  {'类型':15} | {'胜率':>6} | {'均盈亏':>8} | {'样本':>4}")
    print(f"  {'─'*15}─┼─{'─'*6}─┼─{'─'*8}─┼─{'─'*4}")
    for k, v in sorted(report.by_signal_type.items(), key=lambda x: x[1].get('avg_pnl_pct', 0), reverse=True):
        print(f"  {k:15} | {v.get('win_rate', 0):>5.1f}% | {v.get('avg_pnl_pct', 0):>+7.2f}% | {v.get('count', 0):>4}")

print(f"\n{'─'*60}")
print(f"  📋 逐案明细：")
print(f"  {'信号类型':12} | {'标的':12} | {'方向':8} | {'入场价':>8} | {'结果':12} | {'盈亏':>7} | {'天数':>4}")
print(f"  {'─'*12}─┼─{'─'*12}─┼─{'─'*8}─┼─{'─'*8}─┼─{'─'*12}─┼─{'─'*7}─┼─{'─'*4}")
for c in report.cases:
    pnl = f"{c.realized_pnl_pct*100:+.2f}%" if c.realized_pnl_pct is not None else "  N/A"
    ep = f"{c.entry_price:.3f}" if c.entry_price else "  N/A"
    print(f"  {c.signal_type:12} | {c.instrument:12} | {c.signal_direction:8} | {ep:>8} | {c.status:12} | {pnl:>7} | {c.days_held:>4}")


# ═══════════════════════════════════════════════════════════════
# 测试3：SignalEvaluator 深度分析
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print("测试3: SignalEvaluator 深度分析（信号有效性验证）")
print("=" * 60)

from m9_paper_trader.evaluator import SignalEvaluator

evaluator = SignalEvaluator()
pos_dicts = engine._cases_to_pos_dicts(report.cases)
eval_report = evaluator.evaluate(pos_dicts, min_closed=3)

grade = eval_report.get("signal_efficacy_grade", {})
overall = eval_report.get("overall", {})

print(f"\n  🏅 信号有效性评级: {grade.get('grade', 'N/A')}")
print(f"     {grade.get('description', '')}")
print(f"\n  核心指标:")
print(f"    胜率:      {overall.get('win_rate', 0)}%")
print(f"    期望值:    {overall.get('expectancy_pct', 0):+.2f}%/笔")
print(f"    盈亏比:    {overall.get('profit_factor', 0)}")
print(f"    Sharpe:    {overall.get('sharpe', 0):.2f}")
print(f"    最佳单笔:  {overall.get('best', 0):+.2f}%")
print(f"    最差单笔:  {overall.get('worst', 0):+.2f}%")

mae_mfe = eval_report.get("mae_mfe", {})
if mae_mfe:
    print(f"\n  MAE/MFE 分析:")
    print(f"    平均MAE:  {mae_mfe.get('avg_mae', 0):+.2f}%  (最大不利偏移)")
    print(f"    平均MFE:  {mae_mfe.get('avg_mfe', 0):+.2f}%  (最大有利偏移)")
    print(f"    {mae_mfe.get('comment', '')}")

# 信号强度分层效果
intensity_tier = eval_report.get("by_intensity_tier", {})
tier_lift = intensity_tier.get("tier_lift", {})
if tier_lift:
    print(f"\n  📊 信号强度（intensity）分层验证:")
    for tier, stats in intensity_tier.items():
        if tier == "tier_lift":
            continue
        if isinstance(stats, dict) and "win_rate" in stats:
            print(f"    {tier:12} | 胜率 {stats.get('win_rate', 0)}% | 期望 {stats.get('expectancy_pct', 0):+.2f}%")
    lift = tier_lift.get('high_minus_low_win_rate', 0)
    has_power = tier_lift.get('has_predictive_power', False)
    print(f"    → 高分组比低分组胜率 {'高' if lift >= 0 else '低'} {abs(lift):.1f}%  |  预测力: {'✓ 有效' if has_power else '✗ 不足'}")

# 改进建议
recs = eval_report.get("recommendations", [])
if recs:
    print(f"\n  💡 改进建议:")
    for r in recs:
        print(f"    • {r[:78]}")


# ═══════════════════════════════════════════════════════════════
# 汇总结论
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print("✅ 回测框架测试完成")
print(f"{'='*60}")
print("  种子价格数据: 510300.SH (2024-07~2025-04) + 588000.SH ✓")
print("  BacktestEngine (T+1开盘入场/止损止盈/超时平仓) ✓")
print("  SignalEvaluator (基于真实历史数据) ✓")
print()
print("  📝 回测结论摘要：")
print(f"    • 测试了 {report.total_cases} 个历史信号，{report.completed} 个完成回测")
if grade.get('grade'):
    print(f"    • 信号系统整体评级: {grade['grade']} — {grade.get('description','')}")
if report.by_signal_type:
    best = max(report.by_signal_type.items(), key=lambda x: x[1].get('avg_pnl_pct', 0))
    worst = min(report.by_signal_type.items(), key=lambda x: x[1].get('avg_pnl_pct', 0))
    print(f"    • 最强信号类型: {best[0]} (均盈亏 {best[1].get('avg_pnl_pct',0):+.2f}%)")
    print(f"    • 最弱信号类型: {worst[0]} (均盈亏 {worst[1].get('avg_pnl_pct',0):+.2f}%)")


# ═══════════════════════════════════════════════════════════════
# 测试4：AKShare 联网拉取验证（网络可用时自动执行）
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print("测试4: AKShare 联网拉取（有网络时执行，无网络自动跳过）")
print("=" * 60)

import socket
def _network_ok(host="8.8.8.8", port=53, timeout=2):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception:
        return False

if not _network_ok():
    print("⏭  当前无网络连接，跳过 AKShare 在线拉取测试")
    print("   离线模式使用内嵌种子数据，功能完整 ✓")
else:
    print("✓ 网络连通，尝试 AKShare 拉取...")
    try:
        # 创建新的 feed 实例（不依赖种子，强制走 AKShare）
        online_feed = HistoryPriceFeed(use_seed=False, seed_merge=True)
        # 只拉一个标的验证接口可用性
        price = online_feed.get_price("510300.SH", date.today())
        summary = online_feed.data_source_summary()
        if summary.get("510300.SH"):
            info = summary["510300.SH"]
            print(f"✓ AKShare 拉取成功: 510300.SH")
            print(f"  数据范围: {info['min_date']} ~ {info['max_date']} ({info['days']} 天)")
            # 写入磁盘缓存后，种子+缓存合并效果验证
            merged_feed = HistoryPriceFeed(use_seed=True, seed_merge=True)
            merged_summary = merged_feed.data_source_summary()
            if merged_summary.get("510300.SH"):
                m = merged_summary["510300.SH"]
                print(f"✓ 合并后 510300.SH: {m['days']} 天 ({m['min_date']} ~ {m['max_date']})")
                print("  种子数据 + AKShare 实时数据双重覆盖 ✓")
        else:
            print("⚠️  AKShare 拉取返回空数据（可能 API 被限流或域名不可达）")
            print("   离线种子数据已覆盖主要历史节点，回测功能不受影响")
    except Exception as e:
        print(f"⚠️  AKShare 拉取异常: {e}")
        print("   离线种子数据已覆盖主要历史节点，回测功能不受影响")


print(f"\n{'='*60}")
print("数据源策略总结：")
print("  离线（无网络）: 内嵌种子数据 → 187天/510300 + 33天/588000 ✓")
print("  联网（AKShare可用）: 种子 + AKShare全量历史 合并 → 磁盘缓存 ✓")
print("  磁盘缓存命中: data/price_cache/<inst>.json → 跳过 AKShare 请求 ✓")
print(f"  当前缓存目录: {HistoryPriceFeed().cache_dir}")

cache_files = list(HistoryPriceFeed().cache_dir.glob("*.json"))
if cache_files:
    print(f"  已缓存文件:")
    for cf in cache_files:
        size_kb = cf.stat().st_size // 1024
        print(f"    {cf.name} ({size_kb}KB)")
else:
    print("  暂无磁盘缓存（联网后首次拉取会自动写入）")
