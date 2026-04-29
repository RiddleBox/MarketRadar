import json
from pathlib import Path

print("=== 实时验证进展 ===\n")

# 检查 live_validation 报告
lv_dir = Path("live_validation")
reports = sorted(lv_dir.glob("report_*.json"))
print(f"每日报告: {len(reports)} 个")
for r in reports:
    print(f"  - {r.name}")

# 检查模拟盘持仓
pos_file = Path("data/paper_positions.json")
if pos_file.exists():
    with open(pos_file, 'r', encoding='utf-8') as f:
        positions = json.load(f)
    print(f"\n模拟盘持仓: {len(positions)} 个")
    for p in positions:
        pnl = p.get("unrealized_pnl_pct", 0) or 0
        status = p.get("status", "UNKNOWN")
        print(f"  {p['instrument']}: {status} | 入场:{p['entry_price']} | 当前:{p['current_price']} | 盈亏:{pnl*100:+.2f}%")
else:
    print("\n模拟盘: 无持仓")

# 检查交易日志
log_file = Path("data/paper_trade_log.json")
if log_file.exists():
    with open(log_file, 'r', encoding='utf-8') as f:
        logs = json.load(f)
    print(f"\n交易日志: {len(logs)} 条")
    for log in logs[-5:]:
        print(f"  [{log.get('timestamp', 'N/A')}] {log.get('instrument', 'N/A')}: {log.get('action', 'N/A')}")
else:
    print("\n交易日志: 无记录")
