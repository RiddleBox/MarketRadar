"""
backtest/normalize_csv_cache.py — 标准化 csv_cache 文件名

把中文别名/非标准文件名转换为按 instrument 命名的 CSV，
方便 HistoryPriceFeed 与后续回测统一消费。
"""
from __future__ import annotations

import json
from pathlib import Path

ALIAS_TO_INSTRUMENT = {
    "沪深300ETF": "510300.SH",
    "上证50ETF": "510050.SH",
    "创业板ETF": "159915.SZ",
    "创业板指ETF": "159915.SZ",
    "创业板50ETF": "159949.SZ",
    "中证500ETF": "510500.SH",
    "科创50ETF": "588000.SH",
    "半导体ETF": "512480.SH",
    "新能源车ETF": "515030.SH",
    "锂电池ETF": "159755.SZ",
    "人工智能AI主题ETF": "515980.SH",
    "人工智能ETF": "515980.SH",
    "中证基建指数ETF": "516950.SH",
    "基建ETF": "516950.SH",
}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    csv_dir = root / "data" / "csv_cache"
    csv_dir.mkdir(parents=True, exist_ok=True)

    created = []
    skipped = []

    for file_path in sorted(csv_dir.glob("*_daily.csv")):
        stem = file_path.stem
        alias = stem[:-6] if stem.endswith("_daily") else stem
        instrument = ALIAS_TO_INSTRUMENT.get(alias)
        if not instrument:
            skipped.append({"source": file_path.name, "reason": "unknown_alias"})
            continue

        target = csv_dir / f"{instrument}_daily.csv"
        if not target.exists():
            target.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")
            created.append({"source": file_path.name, "target": target.name, "instrument": instrument})
        else:
            skipped.append({"source": file_path.name, "reason": "target_exists", "target": target.name})

    report = {
        "csv_dir": str(csv_dir),
        "created": created,
        "skipped": skipped,
    }
    out = root / "data" / "backtest" / "normalize_csv_cache_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[NormalizeCSV] report={out}")


if __name__ == "__main__":
    main()
