"""
tests/_full_pipeline_test.py — M1→M2→M3→M4 完整流程测试

验证：
  1. M1 解码信号
  2. M2 写入 SQLite，读回验证
  3. M3 拿到历史信号参考，输出机会
  4. M4 生成行动计划
  5. 第二批次：历史信号参与 M3 判断
"""
import os, sys, time
os.environ["DEEPSEEK_API_KEY"] = "sk-6c899392de5444369b4518e8c64aa940"
sys.path.insert(0, r"D:\AIproject\MarketRadar")

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from core.llm_client import LLMClient
from core.schemas import SourceType, Market
from m1_decoder.decoder import SignalDecoder
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from m4_action.action_designer import ActionDesigner

NEWS_BATCH_1 = """
【财联社2026年4月13日讯】中国人民银行今日发布公告，决定将7天期逆回购操作利率由此前的1.80%
下调至1.55%，降幅25个基点，为2023年以来首次单次降息幅度超过20bp。

与此同时，沪深港通北向资金当日净流入达到168.7亿元人民币，为近三个月单日最大净流入规模。
其中沪股通净流入102.3亿元，深股通净流入66.4亿元。金融、消费、新能源板块获得主力资金净买入。

Wind数据显示，截至收盘，上证综指上涨2.13%，收于3412点；深证成指涨2.67%；
创业板指涨3.12%，成交额较上个交易日放量41%。
"""

NEWS_BATCH_2 = """
【财联社2026年4月14日讯】昨日央行降息后，今日市场延续强势。
沪深两市继续放量，全天成交额达到1.2万亿元，连续两日超万亿。
北向资金今日净流入85.3亿元，累计两日净流入超250亿元。

国家发改委今日表示，将加快推进基础设施投资，重点支持新能源、数字经济等战略性产业。
下周将召开专项会议研究部署，市场预计相关政策文件将于月内出台。

半导体板块今日领涨，中芯国际A股涨停，北方华创上涨8.6%。科创50指数涨幅达4.1%。
"""

BATCH_1 = "full_test_batch_001"
BATCH_2 = "full_test_batch_002"

# 使用临时数据库，不污染正式数据
tmpdir = tempfile.mkdtemp()
DB_PATH = Path(tmpdir) / "test_signals.db"
print(f"测试数据库: {DB_PATH}")

client = LLMClient()
decoder = SignalDecoder(llm_client=client)
store = SignalStore(db_file=DB_PATH)
engine = JudgmentEngine(llm_client=client)
designer = ActionDesigner(llm_client=client)
markets = [Market.A_SHARE, Market.HK]

# ══════════════════════════════════════════════════════════════
# 批次 1
# ══════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("BATCH 1: 央行降息 + 北向资金流入")
print("="*60)

# M1
print("\n[M1] 解码信号...")
t0 = time.time()
signals_b1 = decoder.decode(NEWS_BATCH_1, "news_batch1", SourceType.NEWS, BATCH_1)
print(f"  → {len(signals_b1)} 条信号 ({time.time()-t0:.1f}s)")
for s in signals_b1:
    print(f"     [{s.signal_type.value}] {s.signal_label} | {s.signal_direction.value} 强:{s.intensity_score} 信:{s.confidence_score}")

# M2 写入
print("\n[M2] 写入 Signal Store...")
saved = store.save(signals_b1)
print(f"  → 写入 {saved} 条")

# M2 读回验证
loaded = store.get_by_batch(BATCH_1)
assert len(loaded) == saved, f"读回数量不匹配: {len(loaded)} vs {saved}"
print(f"  → 读回验证 ✓ ({len(loaded)} 条，数据一致)")

stats = store.stats()
print(f"  → Signal Store 统计: 总计 {stats['total']} 条 | 批次: {stats['recent_batches']}")

# M3（无历史参考）
print("\n[M3] 机会判断（无历史参考）...")
t1 = time.time()
opps_b1 = engine.judge(signals=signals_b1, historical_signals=None, batch_id=BATCH_1)
print(f"  → {len(opps_b1)} 个机会 ({time.time()-t1:.1f}s)")
for opp in opps_b1:
    print(f"     [{opp.priority_level.value}] {opp.opportunity_title}")
    print(f"     论点: {opp.opportunity_thesis[:80]}...")

# M4
if opps_b1:
    print("\n[M4] 行动设计...")
    for opp in opps_b1:
        t2 = time.time()
        plan = designer.design(opp)
        print(f"  [{opp.priority_level.value}] {opp.opportunity_title}")
        print(f"    标的: {plan.primary_instruments[:3]}")
        print(f"    止损: {plan.stop_loss.stop_loss_type} {plan.stop_loss.stop_loss_value}% | {plan.stop_loss.notes}")
        print(f"    止盈: {plan.take_profit.take_profit_type} {plan.take_profit.take_profit_value}%")
        print(f"    仓位: {plan.position_sizing.suggested_allocation} (上限 {plan.position_sizing.max_allocation})")
        print(f"    行动阶段:")
        for ph in plan.phases:
            print(f"      [{ph.phase_name}] {ph.timing_description} (仓位比 {ph.allocation_ratio*100:.0f}%)")
        print(f"    有效至: {plan.valid_until.strftime('%Y-%m-%d')} ({time.time()-t2:.1f}s)")

# ══════════════════════════════════════════════════════════════
# 批次 2（有历史参考）
# ══════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("BATCH 2: 政策跟进 + 半导体领涨（有批次1历史参考）")
print("="*60)

# M1
print("\n[M1] 解码信号...")
t0 = time.time()
signals_b2 = decoder.decode(NEWS_BATCH_2, "news_batch2", SourceType.NEWS, BATCH_2)
print(f"  → {len(signals_b2)} 条信号 ({time.time()-t0:.1f}s)")
for s in signals_b2:
    print(f"     [{s.signal_type.value}] {s.signal_label} | {s.signal_direction.value} 强:{s.intensity_score}")

# M2 写入
print("\n[M2] 写入 Signal Store...")
saved2 = store.save(signals_b2)
print(f"  → 写入 {saved2} 条")

stats2 = store.stats()
print(f"  → Signal Store 统计: 总计 {stats2['total']} 条")

# 从 M2 检索历史信号（排除当前批次）
hist = store.get_by_time_range(
    start=datetime.now() - timedelta(days=7),
    end=datetime.now(),
    markets=markets,
    min_intensity=1,
)
current_ids = {s.signal_id for s in signals_b2}
hist = [s for s in hist if s.signal_id not in current_ids]
print(f"\n[M2→M3] 历史参考信号: {len(hist)} 条（来自批次1）")

# M3（有历史参考）
print("\n[M3] 机会判断（有历史参考）...")
t1 = time.time()
opps_b2 = engine.judge(signals=signals_b2, historical_signals=hist if hist else None, batch_id=BATCH_2)
print(f"  → {len(opps_b2)} 个机会 ({time.time()-t1:.1f}s)")
for opp in opps_b2:
    print(f"     [{opp.priority_level.value}] {opp.opportunity_title}")
    print(f"     论点: {opp.opportunity_thesis[:100]}...")
    if opp.related_signals:
        print(f"     关联信号: {opp.related_signals[:3]}")

# M4
if opps_b2:
    print("\n[M4] 行动设计...")
    for opp in opps_b2:
        plan = designer.design(opp)
        print(f"  [{opp.priority_level.value}] {opp.opportunity_title}")
        print(f"    标的: {plan.primary_instruments[:3]}")
        print(f"    仓位: {plan.position_sizing.suggested_allocation}")
        print(f"    阶段: {[ph.phase_name for ph in plan.phases]}")

# ══════════════════════════════════════════════════════════════
print("\n" + "="*60)
print(f"全流程完成 ✓")
print(f"  批次1: {len(signals_b1)} 信号 → {len(opps_b1)} 机会")
print(f"  批次2: {len(signals_b2)} 信号 + {len(hist)} 历史信号 → {len(opps_b2)} 机会")
print(f"  Signal Store 总计: {stats2['total']} 条信号")
print("="*60)
