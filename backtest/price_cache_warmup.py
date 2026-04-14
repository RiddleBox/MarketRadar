"""
backtest/price_cache_warmup.py — Reality backtest price cache warmup

目标：
- 扫描 data/opportunities/*.json 中真实样本使用的标的
- 标准化 instrument 代码
- 通过 HistoryPriceFeed 批量预热 data/price_cache/*.json
- 输出成功/失败摘要，便于随后重跑 reality_backtest_phase1

用法：
  python -m backtest.price_cache_warmup
  python -m backtest.price_cache_warmup --opp-dir data/opportunities --use-seed
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backtest.history_price import HistoryPriceFeed
from backtest.market_price_resolver import get_market_price_plan

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPP_DIR = ROOT / "data" / "opportunities"
DEFAULT_CACHE_DIR = ROOT / "data" / "price_cache"
DEFAULT_OUT_DIR = ROOT / "data" / "backtest"


ALIASES = {
    "沪深300ETF": "510300.SH",
    "上证50ETF": "510050.SH",
    "中证500ETF": "510500.SH",
    "创业板ETF": "159915.SZ",
    "创业板指ETF": "159915.SZ",
    "创业板50ETF": "159949.SZ",
    "科创50ETF": "588000.SH",
    "科创50指数": "588000.SH",
    "半导体ETF": "512480.SH",
    "半导体ETF(512480)": "512480.SH",
    "半导体ETF（512480）": "512480.SH",
    "新能源车ETF": "515030.SH",
    "新能源车主题ETF": "515030.SH",
    "锂电池ETF": "159755.SZ",
    "锂电池ETF(159755)": "159755.SZ",
    "锂电池ETF（159755）": "159755.SZ",
    "人工智能AI主题ETF": "515980.SH",
    "中证基建指数ETF": "516950.SH",
    "中芯国际": "688981.SH",
    "中芯国际A股": "688981.SH",
    "恒生科技指数期货": "3033.HK",
}


def normalize_instrument(raw_inst: str) -> str:
    text = str(raw_inst or "").strip()
    if not text:
        return text
    if text in ALIASES:
        return ALIASES[text]

    import re

    m = re.search(r"(\d{5,6})\.(SH|SZ|HK)", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}.{m.group(2).upper()}"

    m = re.search(r"[（(](\d{5,6})(?:\.(HK))?[）)]", text, re.IGNORECASE)
    if m:
        code = m.group(1)
        if m.group(2):
            return f"{code}.HK"
        suffix = "SH" if code.startswith(("5", "6")) else "SZ"
        return f"{code}.{suffix}"

    if re.fullmatch(r"\d{6}", text):
        suffix = "SH" if text.startswith(("5", "6")) else "SZ"
        return f"{text}.{suffix}"

    return text


def collect_instruments(opp_dir: Path) -> tuple[list[str], dict[str, list[str]]]:
    result: list[str] = []
    by_market: dict[str, list[str]] = {}
    if not opp_dir.exists():
        return result, by_market
    for f in sorted(opp_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            for opp in items:
                if not isinstance(opp, dict):
                    continue
                markets = opp.get("target_markets") or ["A_SHARE"]
                market = str(markets[0]) if markets else "A_SHARE"
                insts = opp.get("target_instruments") or opp.get("primary_instruments") or []
                for inst in insts:
                    norm = normalize_instrument(inst)
                    if norm:
                        result.append(norm)
                        by_market.setdefault(market, []).append(norm)
        except Exception:
            continue
    return sorted(set(result)), {k: sorted(set(v)) for k, v in by_market.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--opp-dir", default=str(DEFAULT_OPP_DIR))
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--use-seed", action="store_true")
    args = parser.parse_args()

    opp_dir = Path(args.opp_dir)
    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    instruments, instruments_by_market = collect_instruments(opp_dir)
    feed = HistoryPriceFeed(cache_dir=cache_dir, use_seed=args.use_seed)

    successes = []
    failures = []
    for inst in instruments:
        try:
            feed.preload([inst])
            summary = feed.data_source_summary().get(inst, {})
            if summary.get("days", 0) > 0:
                successes.append({"instrument": inst, **summary})
            else:
                failures.append({"instrument": inst, "reason": "no_data_after_preload"})
        except Exception as e:
            failures.append({"instrument": inst, "reason": str(e)})

    market_source_plan = {m: get_market_price_plan(m).__dict__ for m in instruments_by_market.keys()}

    payload = {
        "opportunity_dir": str(opp_dir),
        "instrument_count": len(instruments),
        "instruments": instruments,
        "instruments_by_market": instruments_by_market,
        "market_source_plan": market_source_plan,
        "successes": successes,
        "failures": failures,
    }
    out_path = out_dir / "price_cache_warmup_report.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[Warmup] instruments={len(instruments)} success={len(successes)} failure={len(failures)}")
    print(f"[Warmup] report={out_path}")


if __name__ == "__main__":
    main()
