from datetime import date

import pandas as pd

from m17_tenbagger_research.sample_discovery import (
    discover_from_price_frames,
    merge_windows_into_episodes,
    scan_qualifying_windows,
)


def test_scan_uses_next_trading_day_after_90_natural_days():
    frame = pd.DataFrame(
        [
            {"date": "2021-01-01", "close": 1.0, "adj_close": 1.0},
            {"date": "2021-04-02", "close": 11.0, "adj_close": 11.0},
        ]
    )

    windows = scan_qualifying_windows(frame, "TEST")

    assert len(windows) == 1
    assert windows[0].target_end_date == date(2021, 4, 1)
    assert windows[0].end_date == date(2021, 4, 2)
    assert windows[0].qualification_basis == "both"
    assert windows[0].quality_tier == "BOTH_QUALIFIED"
    assert windows[0].return_90d == 10.0


def test_scan_dual_records_raw_adjusted_and_flags_single_basis_review():
    frame = pd.DataFrame(
        [
            {"date": "2021-01-01", "close": 1.0, "adj_close": 1.0},
            {"date": "2021-04-01", "close": 11.0, "adj_close": 5.0},
        ]
    )

    windows = scan_qualifying_windows(frame, "RAW")

    assert len(windows) == 1
    assert windows[0].raw_return_90d == 10.0
    assert windows[0].adjusted_return_90d == 4.0
    assert windows[0].qualification_basis == "raw"
    assert windows[0].quality_tier == "RAW_ONLY_REVIEW"
    assert windows[0].needs_manual_review is True


def test_merge_same_ticker_windows_when_start_gap_is_less_than_90_days():
    frame = pd.DataFrame(
        [
            {"date": "2021-01-01", "close": 1.0, "adj_close": 1.0},
            {"date": "2021-01-15", "close": 1.0, "adj_close": 1.0},
            {"date": "2021-04-01", "close": 11.0, "adj_close": 11.0},
            {"date": "2021-04-15", "close": 11.0, "adj_close": 11.0},
            {"date": "2021-04-30", "close": 1.0, "adj_close": 1.0},
            {"date": "2021-07-29", "close": 11.0, "adj_close": 11.0},
        ]
    )
    windows = scan_qualifying_windows(frame, "MERGE")

    episodes = merge_windows_into_episodes(windows)

    assert len(windows) == 3
    assert len(episodes) == 2
    assert episodes[0].num_qualifying_windows == 2
    assert episodes[1].num_qualifying_windows == 1


def test_discover_from_price_frames_returns_windows_and_episodes():
    frames = {
        "AAA": pd.DataFrame(
            [
                {"date": "2021-01-01", "close": 1.0, "adj_close": 1.0},
                {"date": "2021-04-01", "close": 11.0, "adj_close": 11.0},
            ]
        ),
        "BBB": pd.DataFrame(
            [
                {"date": "2021-01-01", "close": 1.0, "adj_close": 1.0},
                {"date": "2021-04-01", "close": 2.0, "adj_close": 2.0},
            ]
        ),
    }

    windows, episodes = discover_from_price_frames(
        frames,
        metadata={"AAA": {"company_name": "AAA Corp", "exchange": "NASDAQ"}},
        data_source="synthetic",
    )

    assert [window.ticker for window in windows] == ["AAA"]
    assert len(episodes) == 1
    assert episodes[0].ticker == "AAA"
    assert episodes[0].company_name == "AAA Corp"
