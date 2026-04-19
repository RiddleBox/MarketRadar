"""
tests/run_verification.py — 端到端验证脚本

运行所有验证步骤，输出到 test_verification_output.txt
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

results = []

def step(name, fn):
    print(f"\n{'='*60}")
    print(f"STEP: {name}")
    print(f"{'='*60}")
    try:
        result = fn()
        print(f"RESULT: {result}")
        results.append({"step": name, "status": "OK", "result": result})
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"step": name, "status": "FAIL", "error": str(e)})

# Step 1: Signal Store
def check_signals():
    from m2_storage.signal_store import SignalStore
    s = SignalStore()
    stats = s.stats()
    total = stats.get("total", 0)
    by_type = stats.get("by_signal_type", {})
    by_batch = stats.get("recent_batches", {})
    return f"total={total}, by_type={by_type}, recent_batches={len(by_batch)}"

step("Signal Store", check_signals)

# Step 2: Paper Trading
def check_paper_trading():
    from m9_paper_trader.paper_trader import PaperTrader
    p = ROOT / "data" / "paper_positions.json"
    if p.exists():
        t = PaperTrader(save_path=p)
        open_pos = t.list_positions(status="OPEN")
        closed_pos = t.list_positions(status="CLOSED")
        return f"open={len(open_pos)}, closed={len(closed_pos)}"
    return "no positions yet (expected for first run)"

step("Paper Trading", check_paper_trading)

# Step 3: Audit Log
def check_audit():
    from pipeline.audit_store import AuditStore
    store = AuditStore()
    recent = store.get_recent(10)
    stats = store.get_stats(days=7)
    return f"recent_entries={len(recent)}, total_7d={stats['total_entries']}"

step("Audit Log", check_audit)

# Step 4: Confirmation Store
def check_confirmations():
    from pipeline.confirmation_store import ConfirmationStore
    store = ConfirmationStore()
    pending = store.get_pending()
    history = store.list_history(limit=10)
    return f"pending={len(pending)}, history={len(history)}"

step("Confirmation Store", check_confirmations)

# Step 5: Sentiment Store
def check_sentiment():
    from m10_sentiment.sentiment_store import SentimentStore
    from pathlib import Path
    db_path = ROOT / "data" / "sentiment" / "sentiment_history.db"
    if db_path.exists():
        store = SentimentStore(db_path=db_path)
        latest = store.latest(3)
        return f"latest_snapshots={len(latest)}"
    return "sentiment_history.db not found (run sentiment collect first)"

step("Sentiment Store", check_sentiment)

# Step 6: M11 Calibration
def check_calibration():
    from m11_agent_sim.calibration_store import CalibrationStore
    from pathlib import Path
    db_path = ROOT / "data" / "m11" / "calibration_history.db"
    if db_path.exists():
        store = CalibrationStore(db_path=db_path)
        runs = store.list_runs(limit=5)
        return f"calibration_runs={len(runs)}"
    return "calibration_history.db not found (run M11 calibration first)"

step("M11 Calibration Store", check_calibration)

# Step 7: Opportunities
def check_opportunities():
    opp_dir = ROOT / "data" / "opportunities"
    if opp_dir.exists():
        files = list(opp_dir.glob("*.json"))
        return f"opportunity_files={len(files)}"
    return "no opportunities directory"

step("Opportunities", check_opportunities)

# Step 8: End-to-end pipeline
def run_pipeline():
    import tempfile
    from m1_decoder.decoder import SignalDecoder
    from m2_storage.signal_store import SignalStore
    from m3_judgment.judgment_engine import JudgmentEngine
    from m4_action.action_designer import ActionDesigner
    from core.schemas import SourceType

    test_text = (
        "央行宣布于2026年4月20日起下调金融机构存款准备金率0.5个百分点，"
        "预计释放长期流动性约1.2万亿元。同时，中国人民银行决定下调7天逆回购利率10bp至1.7%。"
    )

    # M1
    decoder = SignalDecoder()
    signals = decoder.decode(
        raw_text=test_text,
        source_ref="verification_test",
        source_type=SourceType.POLICY_DOCUMENT,
        batch_id="verify_01",
    )
    assert len(signals) >= 1, f"M1 failed: expected >= 1 signals, got {len(signals)}"

    # M2
    store = SignalStore()
    saved = store.save(signals)
    assert saved >= 1, f"M2 failed: saved {saved} signals"

    # M3
    engine = JudgmentEngine()
    opps = engine.judge(signals, batch_id="verify_01")

    # M4
    if opps:
        designer = ActionDesigner()
        plans = [designer.design(opp) for opp in opps]
        titles = [opp.opportunity_title for opp in opps]
        return f"signals={len(signals)}, opportunities={len(opps)}, plans={len(plans)}, titles={titles}"
    return f"signals={len(signals)}, opportunities=0 (no opportunity detected - valid)"

step("End-to-end Pipeline (M1->M4)", run_pipeline)

# Summary
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
ok_count = sum(1 for r in results if r["status"] == "OK")
fail_count = sum(1 for r in results if r["status"] == "FAIL")
print(f"OK: {ok_count}, FAIL: {fail_count}, TOTAL: {len(results)}")
for r in results:
    status = "OK" if r["status"] == "OK" else "FAIL"
    detail = r.get("result", r.get("error", ""))
    print(f"  [{status}] {r['step']}: {detail}")
