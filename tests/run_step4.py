"""
tests/run_step4.py — 第四步：本地组件验证 + 数据源状态检查

注意：AKShare 网络调用可能因网络限制超时，
此脚本改为验证本地组件状态和数据源配置。
"""
import sys
import warnings
warnings.filterwarnings("ignore")

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
        print(f"ERROR: {type(e).__name__}: {e}")
        results.append({"step": name, "status": "FAIL", "error": str(e)})

# Step 1: AKShare import check
def check_akshare_import():
    import akshare as ak
    return f"akshare version: {ak.__version__} (import OK)"

step("AKShare Import Check", check_akshare_import)

# Step 2: AKShare network test (with timeout)
def test_akshare_network():
    import socket
    try:
        socket.setdefaulttimeout(5)
        import akshare as ak
        # 轻量测试：获取交易日历
        df = ak.tool_trade_date_hist_sina()
        if df is not None and not df.empty:
            return f"AKShare network OK, trade dates available: {len(df)} rows"
        return "AKShare returned empty data"
    except Exception as e:
        return f"AKShare network test failed: {type(e).__name__}: {str(e)[:100]}"

step("AKShare Network Test", test_akshare_network)

# Step 3: LLM config check
def check_llm_config():
    import yaml
    config_path = ROOT / "config" / "llm_config.yaml"
    local_path = ROOT / "config" / "llm_config.local.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    default_provider = config.get("default_provider", "unknown")
    
    local_exists = local_path.exists()
    local_info = ""
    if local_exists:
        with open(local_path, 'r', encoding='utf-8') as f:
            local_config = yaml.safe_load(f)
        provider = local_config.get("provider", "unknown")
        has_key = bool(local_config.get("api_key", ""))
        local_info = f", local override: provider={provider}, has_key={has_key}"
    
    return f"default_provider={default_provider}, local_config={local_exists}{local_info}"

step("LLM Configuration", check_llm_config)

# Step 4: Data source priority
def check_data_sources():
    import yaml
    config_path = ROOT / "config" / "market_config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    active = config.get("active_markets", [])
    tushare_token = "NOT SET"
    try:
        import os
        token = os.environ.get("TUSHARE_TOKEN", "")
        if token:
            tushare_token = f"SET (length={len(token)})"
    except:
        pass
    
    return f"active_markets={active}, TUSHARE_TOKEN={tushare_token}"

step("Data Source Configuration", check_data_sources)

# Step 5: M10 Sentiment Engine (offline mock)
def test_sentiment_engine_mock():
    from m0_collector.providers.sentiment_provider import SentimentSnapshot
    snap = SentimentSnapshot(
        market_up_count=3000, market_down_count=1500,
        northbound_net_flow=80.0,
        avg_comprehensive_score=65.0,
    )
    fg = snap.fear_greed_score()
    direction = snap.direction()
    return f"mock FG={fg:.1f}, direction={direction} (offline calculation OK)"

step("M10 Sentiment Engine (Offline Mock)", test_sentiment_engine_mock)

# Step 6: M11 Event Catalog (offline)
def test_event_catalog():
    from m11_agent_sim.event_catalog import load_event_catalog
    events = load_event_catalog(min_events=50)
    return f"loaded {len(events)} historical events"

step("M11 Event Catalog (Offline)", test_event_catalog)

# Step 7: Workflow phase check
def check_workflow_phase():
    from pipeline.workflows import resolve_phase, WorkflowPhase
    phase = resolve_phase("A_SHARE")
    phase_names = {
        WorkflowPhase.PRE_MARKET: "盘前",
        WorkflowPhase.INTRADAY: "盘中", 
        WorkflowPhase.POST_MARKET: "盘后",
        WorkflowPhase.CLOSED: "休市",
    }
    return f"current phase: {phase_names.get(phase, phase.value)}"

step("Workflow Phase Check", check_workflow_phase)

# Step 8: Database files status
def check_databases():
    dbs = {
        "SignalStore": ROOT / "data" / "signal_store.db",
        "Sentiment": ROOT / "data" / "sentiment" / "sentiment_history.db",
        "Audit": ROOT / "data" / "audit" / "audit_log.db",
        "Confirmation": ROOT / "data" / "confirmation" / "confirmation_requests.db",
        "M11 Calibration": ROOT / "data" / "m11" / "calibration_history.db",
    }
    
    status = []
    for name, path in dbs.items():
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        status.append(f"{name}: {'OK' if exists else 'MISSING'} ({size} bytes)")
    
    return "; ".join(status)

step("Database Files Status", check_databases)

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
