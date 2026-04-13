import os, sys
os.environ["DEEPSEEK_API_KEY"] = "sk-6c899392de5444369b4518e8c64aa940"
sys.path.insert(0, r"D:\AIproject\MarketRadar")

# 直接调用 ingest CLI 的核心逻辑（绕过 click）
from pathlib import Path
from datetime import datetime, timedelta
from core.schemas import Market
from core.llm_client import LLMClient
from m1_decoder.decoder import SignalDecoder
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from m4_action.action_designer import ActionDesigner
from pipeline.ingest import collect_files, ingest_file, infer_source_type
import json

BATCH_ID  = f"ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
INPUT_DIR = Path(r"D:\AIproject\MarketRadar\data\incoming")
MARKETS   = [Market.A_SHARE, Market.HK]

llm_client = LLMClient()
decoder    = SignalDecoder(llm_client=llm_client)
store      = SignalStore()

files = collect_files(INPUT_DIR)
print(f"找到 {len(files)} 个文件: {[f.name for f in files]}")
print(f"批次 ID: {BATCH_ID}\n")

# ── 批量 ingestion（M1 + M2）────────────────────────────────
total_signals = 0
for fp in files:
    print(f"[处理] {fp.name} ...", end=" ", flush=True)
    import time; t0 = time.time()
    result = ingest_file(
        file_path=fp,
        decoder=decoder,
        store=store,
        batch_id=BATCH_ID,
        source_type=infer_source_type(fp),
        markets_str="A_SHARE,HK",
        dry_run=False,
    )
    elapsed = time.time() - t0
    if result["error"]:
        print(f"✗ {result['error']}")
    else:
        print(f"✓ {result['signals']} 条信号 ({elapsed:.1f}s)")
        total_signals += result["signals"]

print(f"\nIngestion 完成: {total_signals} 条信号写入 Signal Store")
stats = store.stats()
print(f"Signal Store 总计: {stats['total']} 条 | 本批次批次分布: {stats['recent_batches']}")

# ── M3 机会判断 ──────────────────────────────────────────────
print("\n" + "="*55)
print("M3 机会判断（基于本批次全部信号）")
print("="*55)

signals = store.get_by_batch(BATCH_ID)
hist = store.get_by_time_range(
    start=datetime.now() - timedelta(days=90),
    end=datetime.now(),
    markets=MARKETS,
    min_intensity=5,
)
current_ids = {s.signal_id for s in signals}
hist = [s for s in hist if s.signal_id not in current_ids]

print(f"当前批次: {len(signals)} 条 | 历史参考: {len(hist)} 条")
print("M3 判断中...", end=" ", flush=True)
t0 = time.time()
opps = JudgmentEngine(llm_client=llm_client).judge(
    signals=signals,
    historical_signals=hist or None,
    batch_id=BATCH_ID,
)
print(f"{len(opps)} 个机会 ({time.time()-t0:.1f}s)")

# ── M4 行动设计 ──────────────────────────────────────────────
designer = ActionDesigner(llm_client=llm_client)
plans = []
for opp in opps:
    print(f"\n  [{opp.priority_level.value.upper()}] {opp.opportunity_title}")
    print(f"  市场: {[m.value for m in opp.target_markets]} | 方向: {opp.trade_direction.value}")
    print(f"  论点: {opp.opportunity_thesis[:100]}...")
    print(f"  为什么现在: {opp.why_now[:80]}...")
    print(f"  关键假设: {opp.key_assumptions[:2]}")
    print("  M4 设计行动计划...", end=" ", flush=True)
    t0 = time.time()
    plan = designer.design(opp)
    plans.append(plan)
    print(f"✓ ({time.time()-t0:.1f}s)")
    print(f"    标的: {plan.primary_instruments[:3]}")
    print(f"    仓位: {plan.position_sizing.suggested_allocation} | 止损: {plan.stop_loss.stop_loss_value}% | 止盈: {plan.take_profit.take_profit_value}%")
    print(f"    阶段: {[ph.phase_name for ph in plan.phases]}")

# 保存机会
opp_dir = Path(r"D:\AIproject\MarketRadar\data\opportunities")
opp_dir.mkdir(parents=True, exist_ok=True)
out_file = opp_dir / f"{BATCH_ID}_opportunities.json"
out_file.write_text(
    json.dumps([o.model_dump(mode="json") for o in opps], ensure_ascii=False, indent=2, default=str),
    encoding="utf-8",
)

print(f"\n{'='*55}")
print(f"批量 Pipeline 完成 ✓")
print(f"  文件: {len(files)} | 信号: {total_signals} | 机会: {len(opps)} | 行动计划: {len(plans)}")
print(f"  机会已保存: {out_file}")
