"""
tests/_m9_test.py — M9 模拟盘 + 信号有效性评估测试

测试内容：
  1. PaperTrader 开仓/价格更新/止损止盈触发/持久化
  2. SignalEvaluator 胜率/盈亏比/分层分析/报告生成
  3. MarketSentinel Mock 接入 + 信号转换
  4. 端到端：情绪信号 → 模拟仓 → 平仓 → 评估
"""
import os, sys, json, tempfile, uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, r"D:\AIproject\MarketRadar")

# 使用临时目录，避免污染真实数据
tmpdir = Path(tempfile.mkdtemp())

import m9_paper_trader.paper_trader as pt_mod
pt_mod.PAPER_POS_FILE = tmpdir / "paper_positions.json"

import m9_paper_trader.evaluator as eval_mod
eval_mod.REPORT_DIR = tmpdir / "reports"
eval_mod.REPORT_DIR.mkdir(parents=True)

from m9_paper_trader.paper_trader import PaperTrader, PaperPosition
from m9_paper_trader.evaluator import SignalEvaluator
from integrations.market_sentinel import MockSentinelAdapter, inject_sentiment_signals


# ═══════════════════════════════════════════════════════════════
# 测试1：PaperTrader 基础功能
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("测试1: PaperTrader 开仓/价格更新/止损止盈")
print("=" * 60)

trader = PaperTrader(save_path=tmpdir / "paper_positions.json")

# 手动开立 3 个模拟仓
pp1 = trader.open_manual(
    instrument="510300.SH", market="A_SHARE", direction="BULLISH",
    entry_price=3.80, stop_loss_price=3.61, take_profit_price=4.18,
    quantity=10000, signal_intensity=7.5, signal_confidence=8.0,
    signal_type="macro", opportunity_id="opp_test_001",
)
pp2 = trader.open_manual(
    instrument="512480.SH", market="A_SHARE", direction="BULLISH",
    entry_price=5.20, stop_loss_price=4.94, take_profit_price=6.24,
    quantity=5000, signal_intensity=5.0, signal_confidence=6.0,
    signal_type="policy",
)
pp3 = trader.open_manual(
    instrument="159755.SZ", market="A_SHARE", direction="BEARISH",
    entry_price=1.80, stop_loss_price=1.89, take_profit_price=1.62,
    quantity=20000, signal_intensity=8.0, signal_confidence=7.0,
    signal_type="technical",
)

assert len(trader.list_open()) == 3, "应有3个开仓"
print(f"✓ 开立 3 个模拟仓")
for pp in trader.list_open():
    print(f"  {pp.paper_position_id} | {pp.instrument} | {pp.direction}")

# 更新价格：pp1 上涨 → 触发止盈
pp1.update_price(4.20)
assert pp1.status == "TAKE_PROFIT", f"pp1 应止盈，实际 {pp1.status}"
assert pp1.realized_pnl_pct > 0, "止盈应为正"
print(f"✓ {pp1.instrument} 触发止盈: +{pp1.realized_pnl_pct*100:.2f}%")

# 更新价格：pp2 下跌 → 触发止损
pp2.update_price(4.90)
assert pp2.status == "STOP_LOSS", f"pp2 应止损，实际 {pp2.status}"
assert pp2.realized_pnl_pct < 0, "止损应为负"
print(f"✓ {pp2.instrument} 触发止损: {pp2.realized_pnl_pct*100:.2f}%")

# 更新价格：pp3 下跌（做空方向应上涨）→ 触发止盈
pp3.update_price(1.60)
assert pp3.status == "TAKE_PROFIT", f"pp3 做空应止盈，实际 {pp3.status}"
print(f"✓ {pp3.instrument} 做空止盈: +{pp3.realized_pnl_pct*100:.2f}%")

assert len(trader.list_open()) == 0, "所有仓位应已关闭"
assert len(trader.list_closed()) == 3
print(f"✓ 全部持仓关闭，无残留开仓")

# MAE/MFE 追踪测试
pp_track = trader.open_manual(
    instrument="000001.SZ", market="A_SHARE", direction="BULLISH",
    entry_price=10.00, stop_loss_price=9.50, take_profit_price=11.00,
    quantity=1000,
)
for price in [9.80, 9.70, 10.20, 10.50, 10.80, 11.05]:
    pp_track.update_price(price)

assert pp_track.max_favorable_excursion > 0, "应有正向MFE"
assert pp_track.max_adverse_excursion < 0, "应有负向MAE"
print(f"✓ MAE/MFE 追踪: MAE={pp_track.max_adverse_excursion*100:.2f}% MFE={pp_track.max_favorable_excursion*100:.2f}%")

# 持久化测试
trader._save()
trader2 = PaperTrader(save_path=tmpdir / "paper_positions.json")
assert len(trader2.list_all()) == len(trader.list_all()), "持久化数量不一致"
print(f"✓ 持久化/加载正常 ({len(trader2.list_all())} 条)")


# ═══════════════════════════════════════════════════════════════
# 测试2：SignalEvaluator 统计分析
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("测试2: SignalEvaluator 统计分析")
print("=" * 60)

# 构造 20 条模拟持仓（覆盖多种信号类型）
import random
random.seed(42)

def make_closed_pp(signal_type, intensity, pnl_pct, direction="BULLISH"):
    pp = PaperPosition(
        plan_id=f"plan_{uuid.uuid4().hex[:6]}",
        opportunity_id=f"opp_{uuid.uuid4().hex[:6]}",
        signal_ids=[],
        instrument=f"mock_{uuid.uuid4().hex[:4]}",
        market="A_SHARE",
        direction=direction,
        entry_price=10.0,
        stop_loss_price=9.5 if direction == "BULLISH" else 10.5,
        take_profit_price=None,
        quantity=10000,
        signal_intensity=intensity,
        signal_confidence=intensity * 0.9,
        signal_type=signal_type,
        time_horizon="short",
    )
    pp.realized_pnl_pct = pnl_pct
    pp.max_favorable_excursion = max(pnl_pct, 0.02)
    pp.max_adverse_excursion = min(-0.03, pnl_pct * 0.5)
    pp.status = "TAKE_PROFIT" if pnl_pct > 0 else "STOP_LOSS"
    pp.exit_price = 10.0 * (1 + pnl_pct)
    pp.exit_time = datetime.now()
    return pp

sample_positions = (
    # macro 信号：高强度，胜率好
    [make_closed_pp("macro", 8.0, 0.08)] * 4 +
    [make_closed_pp("macro", 8.0, -0.04)] * 1 +
    # policy 信号：中等
    [make_closed_pp("policy", 6.0, 0.05)] * 3 +
    [make_closed_pp("policy", 6.0, -0.04)] * 2 +
    # technical 信号：低强度，胜率差
    [make_closed_pp("technical", 3.0, 0.03)] * 2 +
    [make_closed_pp("technical", 3.0, -0.05)] * 4 +
    # capital_flow 信号：强度高，胜率较好
    [make_closed_pp("capital_flow", 9.0, 0.10)] * 3 +
    [make_closed_pp("capital_flow", 9.0, -0.03)] * 1
)

evaluator = SignalEvaluator()
report = evaluator.evaluate([p.to_dict() for p in sample_positions], min_closed=5)

overall = report["overall"]
assert overall["win_rate"] > 0, "胜率应大于0"
assert isinstance(overall["profit_factor"], (float, str)), "盈亏比类型错误"
print(f"✓ 整体胜率: {overall['win_rate']}%")
print(f"  期望值: {overall['expectancy_pct']:+.2f}%/笔")
print(f"  盈亏比: {overall['profit_factor']}")
print(f"  Sharpe: {overall['sharpe']}")

# 验证分层有效性
intensity_tier = report.get("by_intensity_tier", {})
tier_lift = intensity_tier.get("tier_lift", {})
print(f"\n✓ 强度分层: 高分组比低分组胜率高 {tier_lift.get('high_minus_low_win_rate', 'N/A')}%")
print(f"  预测力: {'有效' if tier_lift.get('has_predictive_power') else '不足'}")

# 按类型统计
print(f"\n✓ 按信号类型:")
for k, v in report.get("by_signal_type", {}).items():
    print(f"  {k:15} | 胜率 {v.get('win_rate', 0)}% | 期望 {v.get('expectancy_pct', 0):+.2f}% | n={v.get('count', 0)}")

# 评级
grade = report.get("signal_efficacy_grade", {})
print(f"\n✓ 评级: {grade.get('grade', 'N/A')} — {grade.get('description', '')}")

# 改进建议
recs = report.get("recommendations", [])
assert recs, "应有改进建议"
print(f"\n✓ 改进建议 ({len(recs)} 条):")
for r in recs[:3]:
    print(f"  • {r[:70]}...")

# 报告持久化
path = evaluator.save_report(report)
assert path.exists()
print(f"\n✓ 报告已保存: {path.name}")


# ═══════════════════════════════════════════════════════════════
# 测试3：MarketSentinel Mock 接入
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("测试3: MarketSentinel Mock 接入")
print("=" * 60)

# 极度恐惧场景
adapter_fear = MockSentinelAdapter(fear_greed=18.0, northbound=150.0)
reading = adapter_fear.fetch_reading("A_SHARE")
assert reading is not None
assert reading.sentiment_label == "extreme_fear"
assert reading.northbound_flow_1d == 150.0
print(f"✓ 读数获取: FGI={reading.fear_greed_index} ({reading.sentiment_label})")

signals = adapter_fear.to_sentiment_signals(reading, batch_id="test_sentinel")
assert len(signals) >= 2, f"极度恐惧+大额北向应产出至少2条信号，实际{len(signals)}"
print(f"✓ 信号转换: {len(signals)} 条情绪信号")
for s in signals:
    print(f"  {s.signal_id} | {s.signal_direction:8} | 强度={s.intensity_score} | {s.signal_label[:50]}")

# 验证 to_market_signal_dict 格式
d = signals[0].to_market_signal_dict()
required_keys = ["signal_id", "signal_type", "signal_label", "signal_direction",
                 "intensity_score", "confidence_score", "affected_markets"]
for k in required_keys:
    assert k in d, f"缺少字段: {k}"
print(f"✓ MarketSignal 兼容格式验证通过")

# 极度贪婪场景
adapter_greed = MockSentinelAdapter(fear_greed=82.0, northbound=-80.0)
reading2 = adapter_greed.fetch_reading("A_SHARE")
signals2 = adapter_greed.to_sentiment_signals(reading2)
bearish_signals = [s for s in signals2 if s.signal_direction == "BEARISH"]
assert bearish_signals, "贪婪区间应产出看空信号"
print(f"✓ 极度贪婪场景: 产出 {len(bearish_signals)} 条看空信号")


# ═══════════════════════════════════════════════════════════════
# 测试4：端到端 — 情绪信号 → 模拟仓 → 评估
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("测试4: 端到端（情绪信号 → 模拟仓 → 评估）")
print("=" * 60)

# 用情绪信号数据开立模拟仓
e2e_trader = PaperTrader(save_path=tmpdir / "e2e_positions.json")
adapter = MockSentinelAdapter(fear_greed=22.0, northbound=180.0)
reading = adapter.fetch_reading("A_SHARE")
sent_signals = adapter.to_sentiment_signals(reading, batch_id="e2e_test")

# 基于情绪信号开立模拟仓
for sig in sent_signals:
    if sig.signal_direction == "BULLISH" and sig.intensity_score >= 6:
        e2e_trader.open_manual(
            instrument="510300.SH",
            market="A_SHARE",
            direction="BULLISH",
            entry_price=3.90,
            stop_loss_price=3.70,
            take_profit_price=4.29,
            quantity=10000,
            signal_intensity=sig.intensity_score,
            signal_confidence=sig.confidence_score,
            signal_type=sig.signal_type,
            opportunity_id="e2e_opp",
        )

# 模拟价格路径
open_pos = e2e_trader.list_open()
for pp in open_pos:
    pp.update_price(4.30)  # 触发止盈

closed = e2e_trader.list_closed()
assert len(closed) > 0, "应有关闭的模拟仓"

# 评估
e2e_evaluator = SignalEvaluator()
e2e_report = e2e_evaluator.evaluate([p.to_dict() for p in closed], min_closed=1)
e2e_grade = e2e_report.get("signal_efficacy_grade", {})

print(f"✓ 情绪信号开仓: {len(open_pos)} 个")
print(f"✓ 平仓: {len(closed)} 个 ({[p.status for p in closed]})")
print(f"✓ 评级: {e2e_grade.get('grade', 'N/A')}")


# ── 汇总 ─────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("M9 模拟盘 所有测试通过 ✓")
print("  PaperTrader（开仓/止损止盈/MAE-MFE/持久化）✓")
print("  SignalEvaluator（胜率/分层/评级/建议）✓")
print("  MarketSentinel Mock（读数/信号转换/兼容性）✓")
print("  端到端（情绪信号→模拟仓→评估）✓")
