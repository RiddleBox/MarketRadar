from pathlib import Path

from backtest.normalize_csv_cache import ALIAS_TO_INSTRUMENT


def test_csv_alias_map_contains_existing_local_cache_names():
    assert ALIAS_TO_INSTRUMENT["沪深300ETF"] == "510300.SH"
    assert ALIAS_TO_INSTRUMENT["上证50ETF"] == "510050.SH"
    assert ALIAS_TO_INSTRUMENT["创业板ETF"] == "159915.SZ"


def test_standardized_target_name_shape(tmp_path: Path):
    alias = "沪深300ETF"
    inst = ALIAS_TO_INSTRUMENT[alias]
    target = tmp_path / f"{inst}_daily.csv"
    assert target.name == "510300.SH_daily.csv"
