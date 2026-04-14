"""
backtest/reality_backtest_phase1.py — Reality-data backtest Phase 1 runner

目标：
- 优先消费 data/opportunities/*.json 中的真实机会样本
- 使用 backtest/history_price.py 的真实价格链路（price_cache / akshare）
- 输出第一版策略回测结果与样本/缓存摘要

用法：
  python -m backtest.reality_backtest_phase1
  python -m backtest.reality_backtest_phase1 --use-seed
  python -m backtest.reality_backtest_phase1 --opp-dir data/opportunities
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backtest.strategy_backtest import StrategyBacktester

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPP_DIR = ROOT / "data" / "opportunities"
DEFAULT_CACHE_DIR = ROOT / "data" / "price_cache"
DEFAULT_OUT_DIR = ROOT / "data" / "backtest"


def _opportunity_summary(opp_dir: Path) -> dict:
    files = sorted(opp_dir.glob("*.json")) if opp_dir.exists() else []
    sample_keys = []
    total_items = 0
    for f in files[:3]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            total_items += len(items)
            if items and isinstance(items[0], dict):
                sample_keys.append({"file": f.name, "keys": list(items[0].keys())[:12]})
        except Exception:
            sample_keys.append({"file": f.name, "keys": ["<parse_failed>"]})
    if len(files) > 3:
        for f in files[3:]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                items = data if isinstance(data, list) else [data]
                total_items += len(items)
            except Exception:
                pass
    return {
        "exists": opp_dir.exists(),
        "files": len(files),
        "items": total_items,
        "samples": sample_keys,
    }


def _cache_summary(cache_dir: Path) -> dict:
    files = sorted(cache_dir.glob("*.json")) if cache_dir.exists() else []
    sample_ranges = []
    for f in files[:5]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            keys = sorted(data.keys())
            sample_ranges.append({
                "file": f.name,
                "days": len(keys),
                "start": keys[0] if keys else None,
                "end": keys[-1] if keys else None,
            })
        except Exception:
            sample_ranges.append({"file": f.name, "days": -1, "start": None, "end": None})
    return {
        "exists": cache_dir.exists(),
        "files": len(files),
        "samples": sample_ranges,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--opp-dir", default=str(DEFAULT_OPP_DIR))
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--use-seed", action="store_true", help="没有真实价格时允许用 seed 兜底")
    parser.add_argument("--strategies", default="", help="逗号分隔，如 MacroMomentum,PolicyBreakout")
    args = parser.parse_args()

    opp_dir = Path(args.opp_dir)
    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    opp_summary = _opportunity_summary(opp_dir)
    cache_summary = _cache_summary(cache_dir)

    bt = StrategyBacktester(cache_dir=cache_dir, use_seed=args.use_seed)
    events = bt.load_events_from_opportunities(opp_dir)
    if not events:
        print("[Phase1] 未从机会目录加载到任何事件。")
        print(json.dumps({"opportunities": opp_summary, "price_cache": cache_summary}, ensure_ascii=False, indent=2))
        return

    strategy_names = [s.strip() for s in args.strategies.split(",") if s.strip()] or None
    results = bt.run_all(events, strategy_names=strategy_names)
    report = bt.compare_strategies(results)

    payload = {
        "opportunities": opp_summary,
        "price_cache": cache_summary,
        "events_loaded": len(events),
        "event_instruments": sorted({e.instrument for e in events}),
        "event_markets": sorted({e.market for e in events}),
        "report": report,
    }

    out_path = out_dir / "reality_phase1_report.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[Phase1] 机会文件: {opp_summary['files']} 个, 事件加载: {len(events)} 个")
    print(f"[Phase1] 价格缓存文件: {cache_summary['files']} 个")
    print(f"[Phase1] 回测结果已写入: {out_path}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
