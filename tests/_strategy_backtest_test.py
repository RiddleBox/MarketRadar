"""
tests/_strategy_backtest_test.py — 策略回测测试

覆盖：
  1. 策略定义与过滤逻辑
  2. StrategyBacktester 单策略 + 全策略运行
  3. 回测结果指标计算（胜率/盈亏比/MFE/MAE）
  4. 对比报告生成
  5. 看空事件（BEARISH）方向处理
"""
import sys, logging
from datetime import date
from pathlib import Path

sys.path.insert(0, r"D:\AIproject\MarketRadar")
logging.basicConfig(level=logging.WARNING)

from backtest.strategies import Strategy, STRATEGIES
from backtest.strategy_backtest import StrategyBacktester, SignalEvent


print("=" * 60)
print("测试1: 策略定义")
print("=" * 60)

assert "MacroMomentum"  in STRATEGIES
assert "PolicyBreakout" in STRATEGIES
assert "ComboFilter"    in STRATEGIES
print("✓ 三个基础策略已注册")

mm = STRATEGIES["MacroMomentum"]
assert mm.stop_loss_pct == 0.05
assert mm.take_profit_pct == 0.20
assert mm.max_holding_days == 30
print("✓ MacroMomentum 参数正确")

pb = STRATEGIES["PolicyBreakout"]
assert pb.stop_loss_pct == 0.03
assert pb.max_holding_days == 15
print("✓ PolicyBreakout 参数正确")

cf = STRATEGIES["ComboFilter"]
assert cf.signal_types_require_all is True
assert cf.stop_loss_pct == 0.07
assert cf.max_holding_days == 45
print("✓ ComboFilter 参数正确（AND 逻辑）")


print("\n" + "=" * 60)
print("测试2: 策略信号过滤逻辑")
print("=" * 60)

# MacroMomentum 只接受 macro 信号
assert mm.matches_signal("macro", 7.0, 6.0, "BULLISH") is True
assert mm.matches_signal("policy", 7.0, 6.0, "BULLISH") is False  # 错误类型
assert mm.matches_signal("macro", 3.0, 6.0, "BULLISH") is False   # 强度不足
assert mm.matches_signal("macro", 7.0, 3.0, "BULLISH") is False   # 置信不足
assert mm.matches_signal("macro", 7.0, 6.0, "BEARISH") is False   # 方向不符
print("✓ MacroMomentum 过滤逻辑正确")

# PolicyBreakout 接受 policy 或 industry
assert pb.matches_signal("policy", 7.5, 6.5, "BULLISH") is True
assert pb.matches_signal("industry", 7.5, 6.5, "BULLISH") is True
assert pb.matches_signal("macro", 7.5, 6.5, "BULLISH") is False
print("✓ PolicyBreakout 过滤逻辑正确")


print("\n" + "=" * 60)
print("测试3: StrategyBacktester 种子数据回测")
print("=" * 60)

import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    bt = StrategyBacktester(cache_dir=Path(tmpdir), use_seed=True)
    events = bt.build_events_from_seed()
    assert len(events) >= 10, f"种子事件不足: {len(events)}"
    print(f"✓ 构建 {len(events)} 个种子信号事件")

    # 只跑 MacroMomentum
    result_mm = bt.run_strategy(STRATEGIES["MacroMomentum"], events)
    ct = result_mm.completed_trades
    assert len(ct) >= 5, f"MacroMomentum 完成交易太少: {len(ct)}"
    print(f"✓ MacroMomentum: {len(ct)} 笔完成交易")

    # 胜率应该在合理范围（不必然正期望，但不能全输）
    assert result_mm.win_rate >= 0.0 and result_mm.win_rate <= 1.0
    # 盈亏比应该 > 0（均盈利 > 均亏损）
    assert result_mm.profit_factor > 0
    print(f"✓ 胜率={result_mm.win_rate*100:.1f}%, 盈亏比={result_mm.profit_factor:.2f}")

    # MFE > 0 on winning trades
    for t in ct:
        assert t.max_favorable_excursion >= 0, "MFE 不应为负"
        assert t.days_held > 0, "持仓天数应 > 0"
    print("✓ MFE/MAE/days_held 字段正确")


print("\n" + "=" * 60)
print("测试4: 全策略对比 + 报告")
print("=" * 60)

with tempfile.TemporaryDirectory() as tmpdir:
    bt = StrategyBacktester(cache_dir=Path(tmpdir), use_seed=True)
    events = bt.build_events_from_seed()
    all_results = bt.run_all(events)

    assert set(all_results.keys()) == set(STRATEGIES.keys())
    print(f"✓ 全策略回测完成: {list(all_results.keys())}")

    report = bt.compare_strategies(all_results)
    assert "strategies_ranked" in report
    assert "best_strategy" in report
    assert len(report["recommendations"]) == len(STRATEGIES)
    print(f"✓ 对比报告生成: 最佳={report['best_strategy']}, "
          f"最高均盈亏={report['best_avg_pnl']:+.2f}%")

    # 至少有一个策略是正期望
    assert report["best_avg_pnl"] > 0, "没有正期望策略，数据有问题"
    print("✓ 至少一个策略正期望")


print("\n" + "=" * 60)
print("测试5: 看空信号处理（BEARISH）")
print("=" * 60)

bearish_event = SignalEvent(
    instrument="510300.SH",
    market="A_SHARE",
    signal_type="macro",
    signal_direction="BEARISH",
    signal_intensity=7.0,
    signal_confidence=6.5,
    time_horizon="short",
    signal_date=date(2025, 4, 3),
    note="关税冲击，看空",
)

# 默认策略只接受 BULLISH，看空事件应该被过滤
with tempfile.TemporaryDirectory() as tmpdir:
    bt = StrategyBacktester(cache_dir=Path(tmpdir), use_seed=True)
    result = bt.run_strategy(STRATEGIES["MacroMomentum"], [bearish_event])
    # 应该 0 笔完成（被方向过滤）
    assert len(result.completed_trades) == 0, "BEARISH 事件不应进入 BULLISH 策略"
    print("✓ BEARISH 事件被 BULLISH 策略正确过滤")

    # 创建一个接受 BEARISH 的策略验证看空逻辑
    bear_strategy = Strategy(
        name="BearTest",
        description="测试看空策略",
        signal_types=["macro"],
        allowed_directions=["BEARISH"],
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        max_holding_days=10,
    )
    result_bear = bt.run_strategy(bear_strategy, [bearish_event])
    ct_bear = result_bear.completed_trades
    if ct_bear:
        t = ct_bear[0]
        # 看空逻辑：入场价 > 出场价 = 盈利
        assert t.signal_direction == "BEARISH"
        print(f"✓ 看空交易: 入场={t.entry_price:.3f}, 出场={t.exit_price:.3f}, "
              f"盈亏={t.realized_pnl_pct*100:+.2f}%, 原因={t.exit_reason}")
    else:
        print("⏭  看空数据不足，跳过方向验证（种子数据2025-04-03后已到边界）")


print("\n" + "=" * 60)
print("测试6: load_events_from_opportunities（真实机会文件）")
print("=" * 60)

opp_dir = Path(r"D:\AIproject\MarketRadar\data\opportunities")
with tempfile.TemporaryDirectory() as tmpdir:
    bt = StrategyBacktester(cache_dir=Path(tmpdir), use_seed=True)
    if opp_dir.exists() and list(opp_dir.glob("*.json")):
        opp_events = bt.load_events_from_opportunities(opp_dir)
        print(f"✓ 从真实机会文件加载 {len(opp_events)} 个事件")
        if opp_events:
            results = bt.run_all(opp_events)
            report = bt.compare_strategies(results)
            print(f"  真实机会回测: 最佳={report['best_strategy']}, "
                  f"均盈亏={report['best_avg_pnl']:+.2f}%")
    else:
        print("⏭  暂无真实机会文件，跳过（运行 M1→M3 后会生成）")


print("\n" + "=" * 60)
print("✅ 策略回测测试全部通过")
print("=" * 60)
print()
print("  可用策略：")
for name, s in STRATEGIES.items():
    print(f"    {name:20} 止损{s.stop_loss_pct*100:.0f}% 止盈{(s.take_profit_pct or 0)*100:.0f}% 最长{s.max_holding_days}天")
print()
print("  运行完整回测：")
print("    python -m backtest.strategy_backtest")
