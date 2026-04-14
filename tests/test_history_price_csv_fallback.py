from datetime import date
from pathlib import Path

from backtest.history_price import HistoryPriceFeed


def test_history_price_feed_prefers_csv_before_akshare(tmp_path: Path):
    csv_dir = tmp_path / "csv_cache"
    cache_dir = tmp_path / "price_cache"
    csv_dir.mkdir()
    cache_dir.mkdir()

    (csv_dir / "510300.SH_daily.csv").write_text(
        "date,open,high,low,close,volume\n2026-04-10,3.9,4.1,3.8,4.0,1000\n",
        encoding="utf-8",
    )

    feed = HistoryPriceFeed(cache_dir=cache_dir, csv_dir=csv_dir, use_seed=False)
    px = feed.get_price("510300.SH", date(2026, 4, 10), "close")
    assert px == 4.0
