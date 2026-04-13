"""
tests/_integration_test.py — 集成测试

覆盖：
  1. M3 情绪共振检测（SentimentResonanceDetector）
  2. OpenClaw 入口（MarketBriefAnalyzer 规则模式）
  3. LLM 适配器（make_llm_client auto 模式）
  4. 端到端：今日快照 → 共振检测 → 市场简报
"""
import sys, logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.WARNING)

from core.schemas import MarketSignal
from datetime import datetime


# ─────────────────────────────────────────────────────────────
# 工具：构造 MarketSignal
# ─────────────────────────────────────────────────────────────

def make_policy_signal(direction="BULLISH", intensity=8.5) -> MarketSignal:
    return MarketSignal(
        signal_id=f"test_policy_{direction}_{intensity}",
        signal_type="macro",
        signal_label=f"测试政策信号_{direction}",
        description="央行宣布降准50bp+降息15bp，历史性宽松政策组合",
        evidence_text="国新办发布会",
        affected_markets=["A_SHARE"],
        affected_instruments=["510300.SH"],
        signal_direction=direction,
        event_time=datetime.now(),
        collected_time=datetime.now(),
        time_horizon="SHORT",
        intensity_score=int(intensity),
        confidence_score=9,
        timeliness_score=9,
        source_type="official_announcement",
        source_ref="test",
        logic_frame={"what_changed": "测试政策信号", "change_direction": direction, "affects": ["A_SHARE"]},
    )


def make_snapshot(fg=50.0, nb=0.0, adr=0.5) -> dict:
    return {
        "fear_greed_index": fg,
        "northbound_net_billion": nb,
        "advance_decline_ratio": adr,
        "sentiment_label": "中性" if 40 <= fg <= 60 else ("恐惧" if fg < 40 else "贪婪"),
        "weibo_sentiment": 0.0,
        "timestamp": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# 测试 1：情绪共振检测
# ─────────────────────────────────────────────────────────────

print("=" * 60)
print("测试1: M3 情绪共振检测")
print("=" * 60)

from m3_judgment.sentiment_resonance import (
    SentimentResonanceDetector,
    RESONANCE_BULLISH, RESONANCE_BEARISH,
    RESONANCE_POLICY_PANIC, RESONANCE_RECOVERY,
    check_resonance,
)

detector = SentimentResonanceDetector()

# 场景1：极度恐惧 + 强力政策多 → BULLISH 共振（降准场景）
snap_fear_policy = make_snapshot(fg=18.0, nb=120.0, adr=0.72)
signals_policy = [make_policy_signal("BULLISH", 9.5)]
r1 = detector.detect(snap_fear_policy, signals_policy)
assert r1 is not None, "降准+极度恐惧 应触发共振"
assert r1.signal_direction == "BULLISH"
assert r1.signal_type == "sentiment"
assert "逆向" in r1.signal_label or "bullish" in r1.signal_id
print(f"✓ 降准+极度恐惧 → {r1.signal_label} 强度={r1.intensity_score}")

# 场景2：极度贪婪 → BEARISH 过热预警
snap_greed = make_snapshot(fg=85.0, nb=50.0, adr=0.78)
r2 = detector.detect(snap_greed, [])
assert r2 is not None, "极度贪婪 应触发过热预警"
assert r2.signal_direction == "BEARISH"
print(f"✓ 极度贪婪 → {r2.signal_label} 强度={r2.intensity_score}")

# 场景3：政策负面 + 情绪恐惧 → 双杀
snap_bear = make_snapshot(fg=25.0, nb=-90.0, adr=0.30)
signals_bear = [make_policy_signal("BEARISH", 8.0)]
r3 = detector.detect(snap_bear, signals_bear)
assert r3 is not None, "政策负面+情绪恐惧 应触发双杀"
assert r3.signal_direction == "BEARISH"
print(f"✓ 政策双杀 → {r3.signal_label} 强度={r3.intensity_score}")

# 场景4：情绪恐惧 + 北向回流 → 底部修复
snap_recovery = make_snapshot(fg=32.0, nb=45.0, adr=0.52)
r4 = detector.detect(snap_recovery, [])
assert r4 is not None, "情绪恐惧+北向回流 应触发底部修复"
assert r4.signal_direction == "BULLISH"
print(f"✓ 底部修复 → {r4.signal_label} 强度={r4.intensity_score}")

# 场景5：中性区间 → 无共振
snap_neutral = make_snapshot(fg=50.0, nb=10.0, adr=0.50)
r5 = detector.detect(snap_neutral, [])
assert r5 is None, f"中性区间 不应触发共振，实际: {r5}"
print(f"✓ 中性区间 → 无共振（正确）")

# 场景6：信号字段完整性
assert r1.signal_id.startswith("resonance_")
assert r1.source_type == "market_data"
assert r1.time_horizon == "SHORT"
assert r1.batch_id is not None
print(f"✓ 共振信号字段完整性通过")

# check_resonance 便捷函数
r_conv = check_resonance(snap_fear_policy, signals_policy, auto_inject=False)
assert r_conv is not None
assert r_conv.signal_direction == "BULLISH"
print(f"✓ check_resonance() 便捷函数正常")


# ─────────────────────────────────────────────────────────────
# 测试 2：LLM 适配器（规则模式降级）
# ─────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("测试2: LLM 适配器")
print("=" * 60)

from integrations.llm_adapter import make_llm_client, LLMAdapter

# auto 模式：OpenClaw 不可用时降级到 rules
client = make_llm_client(provider="auto", fallback_to_rules=True)
# 在测试环境下可能为 None（降级到规则模式），也可能是 LLMAdapter
if client is None:
    print("✓ auto 模式：所有 LLM 不可用，降级到规则模式（正常）")
else:
    assert isinstance(client, LLMAdapter)
    print(f"✓ auto 模式：获得 {client}")

# fallback_to_rules=True 时不应抛异常
client2 = make_llm_client(provider="openclaw", fallback_to_rules=True)
print(f"✓ openclaw fallback 不崩溃: {client2}")


# ─────────────────────────────────────────────────────────────
# 测试 3：OpenClaw 市场简报（规则模式）
# ─────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("测试3: OpenClaw 市场简报（规则模式）")
print("=" * 60)

from integrations.openclaw_market_brief import MarketBriefAnalyzer, market_brief

analyzer = MarketBriefAnalyzer(use_llm=False)

# get_market_brief（无快照，降级构造默认输入）
brief = analyzer.get_market_brief()
assert "MarketRadar" in brief
assert "综合判断" in brief
assert "Agent 分析链" in brief
print("✓ get_market_brief() 返回有效简报")
print(f"  前3行: {chr(10).join(brief.split(chr(10))[:3])}")

# analyze_event
event_brief = analyzer.analyze_event("央行宣布降准50bp，历史性宽松政策")
assert "MarketRadar" in event_brief
print(f"✓ analyze_event() 返回有效分析")

# quick_verdict
verdict = analyzer.quick_verdict("现在能买入 510300 吗？")
assert "|" in verdict
assert "FG=" in verdict
print(f"✓ quick_verdict(): {verdict}")

# 注入真实快照测试
snap = make_snapshot(fg=18.0, nb=120.0, adr=0.72)

class FakeSentimentStore:
    def latest(self): return snap

import m10_sentiment.sentiment_store as ss_mod
orig = ss_mod.SentimentStore
ss_mod.SentimentStore = FakeSentimentStore

brief_with_snap = analyzer.get_market_brief()
ss_mod.SentimentStore = orig  # 恢复

assert "18" in brief_with_snap or "极度恐惧" in brief_with_snap or "120" in brief_with_snap
print(f"✓ 注入快照后简报含情绪数据")


# ─────────────────────────────────────────────────────────────
# 测试 4：端到端 — 今日快照 → 共振 → 简报 → M11 串联
# ─────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("测试4: 端到端串联（共振 → M11 → 简报）")
print("=" * 60)

from m11_agent_sim.agent_network import AgentNetwork
from m11_agent_sim.schemas import MarketInput, SentimentContext, SignalContext

# 模拟降准场景
snap_dt = make_snapshot(fg=18.0, nb=120.0, adr=0.72)
policy_sig = make_policy_signal("BULLISH", 9.5)

# Step 1: 共振检测
resonance = check_resonance(snap_dt, [policy_sig], auto_inject=False)
assert resonance is not None
assert resonance.signal_direction == "BULLISH"
print(f"✓ Step1 共振: {resonance.signal_label}")

# Step 2: 将共振信号作为背景构建 MarketInput
mi = MarketInput(
    timestamp=datetime(2024, 9, 24),
    market="A_SHARE",
    event_description="央行降准50bp + 情绪共振触发",
    sentiment=SentimentContext(
        fear_greed_index=18.0,
        northbound_flow=120.0,
        advance_decline_ratio=0.72,
    ),
    signals=SignalContext(
        bullish_count=2,  # 政策信号 + 共振信号
        bearish_count=0,
        avg_intensity=9.0,
        avg_confidence=9.0,
        dominant_signal_type="sentiment_resonance",
    ),
)

# Step 3: M11 模拟
net = AgentNetwork._default_a_share(use_llm=False)
dist = net.run(mi)
assert dist.direction == "BULLISH"
assert dist.bullish_prob > 0.55
print(f"✓ Step2 M11: {dist.summary()}")

# Step 4: 格式化简报
brief_e2e = analyzer._format_brief(dist, snap_dt, mi, event_desc="降准+情绪共振")
assert "BULLISH" in brief_e2e or "偏多" in brief_e2e
print(f"✓ Step3 简报: 前2行: {chr(10).join(brief_e2e.split(chr(10))[:2])}")

print("\n" + "=" * 60)
print("所有集成测试通过 ✅")
print("=" * 60)
