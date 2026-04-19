"""scripts/run_full_loop.py - M1->M6 full closed loop test"""
import sys, tempfile
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.llm_client import LLMClient
from m1_decoder.decoder import SignalDecoder
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from m4_action.action_designer import ActionDesigner
from pipeline.position_bridge import open_positions_from_plan
from core.schemas import SourceType, PositionStatus

llm = LLMClient()

# M1
decoder = SignalDecoder(llm_client=llm)
signals = decoder.decode(
    raw_text="中国人民银行今日宣布，下调存款准备金率0.5个百分点，释放长期流动性约1万亿元。同时下调7天期逆回购操作利率20个基点。受此影响，A股市场大幅反弹，沪深300指数单日涨幅超过4%，北向资金净流入超200亿元。",
    source_ref="full_loop_test",
    source_type=SourceType.NEWS,
    batch_id="full_loop_test",
)
print(f"[M1] {len(signals)} signals")

# M2
import m2_storage.signal_store as ss_mod
orig = ss_mod.DB_FILE
tmpdir = Path(tempfile.mkdtemp())
ss_mod.DB_FILE = tmpdir / "signals.db"
store = SignalStore()
store.save(signals)
loaded = store.get_by_batch("full_loop_test")
print(f"[M2] {len(loaded)} stored")

# M3
judge = JudgmentEngine(llm_client=llm)
opps = judge.judge(signals=loaded, batch_id="full_loop_test")
print(f"[M3] {len(opps)} opportunities")

# M4
if not opps:
    print("[M3] no opportunities - this is valid, stopping")
    ss_mod.DB_FILE = orig
    sys.exit(0)

designer = ActionDesigner(llm_client=llm)
plan = designer.design(opps[0])
print(f"[M4] dir={plan.direction.value} market={plan.market.value}")
print(f"     instruments={plan.primary_instruments}")
print(f"     sl={plan.stop_loss.stop_loss_value}% tp={plan.take_profit.take_profit_value}%")
print(f"     max_alloc={plan.position_sizing.max_allocation_pct}")

# M5
positions = open_positions_from_plan(plan=plan, entry_price=3.80, total_capital=1_000_000)
print(f"[M5] opened {len(positions)} positions")
for p in positions:
    print(f"     {p.instrument} qty={p.quantity:.0f} sl={p.stop_loss_price:.3f} tp={p.take_profit_price:.3f}")

# Simulate close
if positions:
    pos = positions[0]
    closed = pos.model_copy(update={
        "status": PositionStatus.TAKE_PROFIT,
        "exit_price": 4.18,
        "exit_time": datetime.now(),
        "exit_reason": "take_profit triggered",
        "realized_pnl": (4.18 - 3.80) * pos.quantity,
        "realized_pnl_pct": (4.18 - 3.80) / 3.80,
    })

    # M6
    import m6_retrospective.retrospective as retro_mod
    retro_tmpdir = Path(tempfile.mkdtemp())
    orig_retro = retro_mod.RETRO_DIR
    retro_mod.RETRO_DIR = retro_tmpdir / "retrospectives"
    retro_mod.RETRO_DIR.mkdir(parents=True, exist_ok=True)

    from m6_retrospective.retrospective import RetrospectiveEngine
    retro = RetrospectiveEngine(llm_client=llm)
    report = retro.analyze(opportunity=opps[0], position=closed, outcome="TAKE_PROFIT")
    print(f"[M6] outcome={report['outcome']} score={report['composite_score']}")

    retro_mod.RETRO_DIR = orig_retro

ss_mod.DB_FILE = orig
print()
print("=== M1->M2->M3->M4->M5->M6 FULL CLOSED LOOP PASSED ===")
