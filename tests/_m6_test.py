"""
tests/_m6_test.py — M6 复盘归因引擎测试

测试：
  1. 单次复盘（基于 M5 关闭的持仓）
  2. 批量复盘扫描
  3. 汇总统计
  4. 不依赖 LLM 的离线验证（结构 + 持久化）
"""
import os, sys, json, tempfile, uuid
from pathlib import Path
from datetime import datetime, timedelta

os.environ["DEEPSEEK_API_KEY"] = "sk-6c899392de5444369b4518e8c64aa940"
sys.path.insert(0, r"D:\AIproject\MarketRadar")

# 临时 retro 目录
tmpdir = Path(tempfile.mkdtemp())

import m6_retrospective.retrospective as retro_mod
retro_mod.RETRO_DIR = tmpdir / "retrospectives"
retro_mod.RETRO_DIR.mkdir(parents=True, exist_ok=True)

from m6_retrospective.retrospective import RetrospectiveEngine
from core.schemas import (
    OpportunityObject, Position, PositionStatus, PriorityLevel,
    Direction, Market, InstrumentType, TimeWindow,
)
from core.llm_client import LLMClient

# ── 构造测试数据 ──────────────────────────────────────────────

def make_opportunity(title="降息驱动A股反弹", priority="research") -> OpportunityObject:
    now = datetime.now()
    return OpportunityObject(
        opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
        opportunity_title=title,
        opportunity_thesis="央行超预期降息25bp，北向资金大幅流入，市场短期情绪改善，构成短线反弹机会。",
        priority_level=PriorityLevel(priority.lower()),
        trade_direction=Direction.BULLISH,
        target_markets=[Market.A_SHARE],
        target_instruments=["沪深300ETF", "上证50ETF"],
        instrument_types=[InstrumentType.ETF],
        opportunity_window=TimeWindow(
            start=datetime.now(),
            end=datetime.now() + timedelta(days=7),
            confidence_level=0.7,
        ),
        why_now="催化剂集中爆发（降息+资金流入+技术突破），市场已即时反应。",
        related_signals=["sig_001", "sig_002", "sig_003"],
        supporting_evidence=["央行超预期降息25bp", "北向资金净流入168亿", "沪深300放量突破"],
        counter_evidence=["外部地缘风险尚存", "经济基本面未见实质改善"],
        key_assumptions=["假设1：政策传导有效，后续专项债按期发行", "假设2：资金流入持续，非一日游"],
        uncertainty_map=["地缘风险发酵可能打断行情"],
        risk_reward_profile="预期盈亏比 2:1，止损-5%，目标+10%",
        next_validation_questions=["专项债发行节奏？", "外资持续流入还是一次性？"],
        judgment_version="1.0",
        created_at=now,
        batch_id="test_batch",
    )


def make_closed_position(
    instrument="510300.SH",
    entry=3.80,
    exit_price=4.18,
    pnl=0.10,
    exit_reason="止盈触发",
) -> Position:
    now = datetime.now()
    opp_id = f"opp_{uuid.uuid4().hex[:8]}"
    plan_id = f"plan_{uuid.uuid4().hex[:8]}"
    return Position(
        plan_id=plan_id,
        opportunity_id=opp_id,
        instrument=instrument,
        instrument_type=InstrumentType.ETF,
        market=Market.A_SHARE,
        direction=Direction.BULLISH,
        quantity=10000.0,
        entry_price=entry,
        current_price=exit_price,
        exit_price=exit_price,
        stop_loss_price=entry * 0.95,
        take_profit_price=entry * 1.10,
        total_cost=entry * 10000,
        unrealized_pnl=pnl,
        realized_pnl=pnl,
        status=PositionStatus.CLOSED,
        entry_time=now - timedelta(days=3),
        exit_time=now,
        exit_reason=exit_reason,
        updates=[],
    )


# ═══════════════════════════════════════════════════════════════
# 测试1：单次复盘（纯结构，mock LLM）
# ═══════════════════════════════════════════════════════════════
print("=" * 55)
print("测试1: 单次复盘（mock LLM，验证结构和持久化）")
print("=" * 55)

class MockLLM:
    def chat_completion(self, messages, **kwargs):
        return json.dumps({
            "signal_quality_score": 4,
            "signal_quality_comment": "信号提取准确，覆盖宏观+资金流+技术三维度",
            "judgment_quality_score": 3,
            "judgment_quality_comment": "论点成立但时机判断略早",
            "timing_quality_score": 4,
            "timing_quality_comment": "入场时机合理，在催化剂出现当日建仓",
            "luck_vs_skill": "主要来自判断力，降息信号解读准确",
            "assumption_verification": "假设1（政策传导）尚未验证；假设2（资金持续流入）已部分验证",
            "key_lesson": "宏观政策信号+资金流共振时，短线反弹胜率高，但需设置严格的时间止损（超过5交易日无突破则离场）",
            "system_improvement": "M3 应新增'时间止损'字段，当机会超过预期窗口仍未兑现时自动降级为 WATCH",
        })

engine = RetrospectiveEngine(llm_client=MockLLM())
opp = make_opportunity()
pos = make_closed_position()
pos.opportunity_id = opp.opportunity_id

report = engine.analyze(opp, pos, outcome="TAKE_PROFIT", notes="按计划止盈")

assert report["retro_id"].startswith("retro_"), f"retro_id 格式错误: {report['retro_id']}"
assert report["outcome"] == "TAKE_PROFIT"
assert report["composite_score"] > 0
assert (retro_mod.RETRO_DIR / f"{report['retro_id']}.json").exists()

print(f"✓ retro_id={report['retro_id']}")
print(f"  综合分={report['composite_score']}/5")
print(f"  已持久化 ✓")
print(f"  教训: {report['analysis']['key_lesson'][:60]}...")
print(f"  改进: {report['analysis']['system_improvement'][:60]}...")

# ═══════════════════════════════════════════════════════════════
# 测试2：批量复盘
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 55)
print("测试2: 批量复盘（3个关闭持仓）")
print("=" * 55)

positions = [
    make_closed_position("510300.SH", 3.80, 4.18, 0.10, "止盈触发"),
    make_closed_position("512480.SH", 5.20, 4.94, -0.05, "止损触发"),
    make_closed_position("159755.SZ", 1.80, 1.96, 0.089, "手动平仓"),
]

opp_map = {}  # 不提供 opp_map，让引擎自动构造最简版本

reports = engine.batch_analyze_closed_positions(
    positions=positions,
    opportunities_map=opp_map,
)
assert len(reports) == 3, f"应生成3份报告，实际{len(reports)}"
print(f"✓ 生成 {len(reports)} 份复盘报告")
for r in reports:
    pnl = r.get("realized_pnl", 0) or 0
    print(f"  {r['instrument']:12} | {r['outcome']:12} | 盈亏 {pnl*100:+.1f}% | 综合分 {r['composite_score']}")

# 重复跑：应被跳过（已有复盘）
reports2 = engine.batch_analyze_closed_positions(positions=positions)
assert len(reports2) == 0, f"重复复盘应全部跳过，实际{len(reports2)}"
print(f"✓ 重复复盘全部跳过（去重正常）")

# ═══════════════════════════════════════════════════════════════
# 测试3：汇总统计
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 55)
print("测试3: 汇总统计")
print("=" * 55)

summary = engine.summarize()
assert summary["total"] == 4, f"应有4份报告（1+3），实际{summary['total']}"
print(f"✓ 复盘总数: {summary['total']}")
print(f"  胜率: {summary['win_rate']}%")
print(f"  平均盈亏: {summary['avg_pnl_pct']:+.2f}%")
print(f"  平均质量分: {summary['avg_composite_score']}/5")
print(f"  结果分布: {summary['outcome_distribution']}")
print(f"  分数分布: {summary['score_distribution']}")

if summary.get("recent_lessons"):
    print(f"  近期教训({len(summary['recent_lessons'])}条):")
    for l in summary["recent_lessons"][:2]:
        print(f"    • {l[:60]}...")

# ═══════════════════════════════════════════════════════════════
# 测试4：outcome 推断
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 55)
print("测试4: 持仓 outcome 自动推断")
print("=" * 55)

cases = [
    (make_closed_position(exit_reason="止盈触发"), "TAKE_PROFIT"),
    (make_closed_position(exit_reason="stop_loss triggered"), "STOP_LOSS"),
    (make_closed_position(pnl=0.08, exit_reason="手动"), "HIT"),
    (make_closed_position(pnl=-0.03, exit_reason="手动"), "MISS"),
]
for pos, expected in cases:
    actual = engine._infer_outcome(pos)
    assert actual == expected, f"推断错误: 期望{expected}，实际{actual}"
    print(f"  ✓ exit_reason='{pos.exit_reason}' pnl={pos.realized_pnl} → {actual}")

# ── 汇总 ────────────────────────────────────────────────────
print("\n" + "=" * 55)
print("M6 复盘归因引擎 所有测试通过 ✓")
print("  单次复盘（结构+持久化）✓")
print("  批量复盘（3持仓，去重）✓")
print("  汇总统计（胜率/均分/分布）✓")
print("  Outcome 自动推断 ✓")
