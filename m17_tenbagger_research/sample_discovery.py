"""Step 1 sample discovery for M17 Ten-Bagger Research."""

from __future__ import annotations

import csv
import math
from bisect import bisect_left
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import pandas as pd

from .schemas import EPISODE_COLUMNS, WINDOW_COLUMNS, Episode, QualifyingWindow


DATE_ALIASES = ("date", "Date", "datetime", "Datetime")
RAW_CLOSE_ALIASES = ("raw_close", "close", "Close", "regular_close")
ADJUSTED_CLOSE_ALIASES = (
    "adjusted_close",
    "adj_close",
    "Adj Close",
    "adjclose",
    "AdjClose",
)
VOLUME_ALIASES = ("volume", "Volume")


def normalize_price_frame(price_frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize provider-specific OHLC frames into M17's daily close schema."""

    if price_frame.empty:
        return pd.DataFrame(
            columns=["date", "raw_close", "adjusted_close", "volume"]
        )

    frame = price_frame.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [
            "_".join(str(part) for part in col if part not in ("", None))
            for col in frame.columns
        ]

    date_values = _extract_date_values(frame)
    raw_close = _extract_numeric_column(frame, RAW_CLOSE_ALIASES)
    adjusted_close = _extract_numeric_column(frame, ADJUSTED_CLOSE_ALIASES)
    volume = _extract_numeric_column(frame, VOLUME_ALIASES)

    normalized = pd.DataFrame(
        {
            "date": pd.to_datetime(date_values).dt.date,
            "raw_close": raw_close,
            "adjusted_close": adjusted_close,
            "volume": volume,
        }
    )
    normalized = normalized.dropna(subset=["date"])
    normalized = normalized[
        normalized[["raw_close", "adjusted_close"]].notna().any(axis=1)
    ]
    normalized = normalized.sort_values("date").drop_duplicates(
        subset=["date"], keep="last"
    )
    normalized = normalized.reset_index(drop=True)
    return normalized


def scan_qualifying_windows(
    price_frame: pd.DataFrame,
    ticker: str,
    *,
    company_name: str = "",
    exchange: str = "",
    data_source: str = "",
    scan_start_date: Optional[date] = None,
    scan_end_date: Optional[date] = None,
    window_days: int = 90,
    min_return: float = 10.0,
) -> list[QualifyingWindow]:
    """Find windows where close price rises at least 1000% over 90 natural days."""

    normalized = normalize_price_frame(price_frame)
    if normalized.empty:
        return []

    trading_dates = list(normalized["date"])
    windows: list[QualifyingWindow] = []

    for idx, start_row in normalized.iterrows():
        start_date = start_row["date"]
        if scan_start_date and start_date < scan_start_date:
            continue
        if scan_end_date and start_date > scan_end_date:
            continue

        target_end_date = start_date + timedelta(days=window_days)
        end_idx = _find_next_trading_day_index(trading_dates, target_end_date)
        if end_idx is None:
            continue

        end_row = normalized.iloc[end_idx]
        raw_return = _calculate_return(
            _optional_float(start_row["raw_close"]),
            _optional_float(end_row["raw_close"]),
        )
        adjusted_return = _calculate_return(
            _optional_float(start_row["adjusted_close"]),
            _optional_float(end_row["adjusted_close"]),
        )

        raw_qualifies = raw_return is not None and raw_return >= min_return
        adjusted_qualifies = (
            adjusted_return is not None and adjusted_return >= min_return
        )
        if not raw_qualifies and not adjusted_qualifies:
            continue

        basis = _qualification_basis(raw_qualifies, adjusted_qualifies)
        windows.append(
            QualifyingWindow(
                ticker=ticker,
                company_name=company_name,
                exchange=exchange,
                start_date=start_date,
                target_end_date=target_end_date,
                end_date=end_row["date"],
                raw_start_price=_optional_float(start_row["raw_close"]),
                raw_end_price=_optional_float(end_row["raw_close"]),
                raw_return_90d=raw_return,
                adjusted_start_price=_optional_float(start_row["adjusted_close"]),
                adjusted_end_price=_optional_float(end_row["adjusted_close"]),
                adjusted_return_90d=adjusted_return,
                qualification_basis=basis,
                data_source=data_source,
                needs_manual_review=basis != "both",
                notes="raw/adjusted qualification mismatch"
                if basis != "both"
                else "",
            )
        )

    return windows


def merge_windows_into_episodes(
    windows: Sequence[QualifyingWindow],
    *,
    max_start_gap_days: int = 90,
) -> list[Episode]:
    """Merge same-ticker qualifying windows when start-date gaps are < 90 days."""

    sorted_windows = sorted(windows, key=lambda item: (item.ticker, item.start_date))
    episodes: list[Episode] = []
    current: list[QualifyingWindow] = []

    for window in sorted_windows:
        if not current:
            current = [window]
            continue

        last = current[-1]
        start_gap = (window.start_date - last.start_date).days
        if window.ticker == last.ticker and start_gap < max_start_gap_days:
            current.append(window)
            continue

        episodes.append(_build_episode(current, len(episodes) + 1))
        current = [window]

    if current:
        episodes.append(_build_episode(current, len(episodes) + 1))

    return episodes


def assign_episode_ids(
    windows: Sequence[QualifyingWindow],
    episodes: Sequence[Episode],
) -> dict[tuple[str, date, date], str]:
    """Build a lookup from window identity to episode id."""

    lookup: dict[tuple[str, date, date], str] = {}
    for episode in episodes:
        episode_windows = [
            window
            for window in windows
            if window.ticker == episode.ticker
            and episode.episode_start_date <= window.start_date <= episode.episode_end_date
        ]
        for window in episode_windows:
            lookup[(window.ticker, window.start_date, window.end_date)] = episode.episode_id
    return lookup


def discover_from_price_frames(
    frames: Mapping[str, pd.DataFrame],
    *,
    metadata: Optional[Mapping[str, Mapping[str, str]]] = None,
    data_source: str = "",
    scan_start_date: Optional[date] = None,
    scan_end_date: Optional[date] = None,
) -> tuple[list[QualifyingWindow], list[Episode]]:
    """Run sample discovery for an in-memory ticker -> price frame mapping."""

    all_windows: list[QualifyingWindow] = []
    metadata = metadata or {}

    for ticker, frame in frames.items():
        ticker_meta = metadata.get(ticker, {})
        all_windows.extend(
            scan_qualifying_windows(
                frame,
                ticker,
                company_name=ticker_meta.get("company_name", ""),
                exchange=ticker_meta.get("exchange", ""),
                data_source=data_source,
                scan_start_date=scan_start_date,
                scan_end_date=scan_end_date,
            )
        )

    episodes = merge_windows_into_episodes(all_windows)
    return all_windows, episodes


def write_windows_csv(
    windows: Sequence[QualifyingWindow],
    path: str | Path,
    *,
    episodes: Sequence[Episode] = (),
) -> None:
    """Write all_tenbaggers.csv-compatible rows."""

    episode_lookup = assign_episode_ids(windows, episodes) if episodes else {}
    rows = [
        window.to_row(
            episode_lookup.get((window.ticker, window.start_date, window.end_date), "")
        )
        for window in windows
    ]
    _write_rows(rows, path)


def write_episodes_csv(episodes: Sequence[Episode], path: str | Path) -> None:
    rows = [episode.to_row() for episode in episodes]
    _write_rows(rows, path)


def _extract_date_values(frame: pd.DataFrame) -> pd.Series:
    date_column = _find_column(frame, DATE_ALIASES)
    if date_column:
        return frame[date_column]
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(frame.index, index=frame.index)
    if frame.index.name and str(frame.index.name).lower() in {"date", "datetime"}:
        return pd.Series(frame.index, index=frame.index)
    raise ValueError("price_frame must contain a date column or a date-like index")


def _extract_numeric_column(
    frame: pd.DataFrame,
    aliases: Iterable[str],
) -> pd.Series:
    column = _find_column(frame, aliases)
    if not column:
        return pd.Series([math.nan] * len(frame), index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _find_column(frame: pd.DataFrame, aliases: Iterable[str]) -> Optional[str]:
    alias_map = {alias.lower(): alias for alias in aliases}
    for column in frame.columns:
        column_name = str(column)
        if column_name.lower() in alias_map:
            return column_name
    return None


def _find_next_trading_day_index(
    trading_dates: Sequence[date],
    target: date,
) -> Optional[int]:
    idx = bisect_left(trading_dates, target)
    if idx >= len(trading_dates):
        return None
    return idx


def _calculate_return(
    start_price: Optional[float],
    end_price: Optional[float],
) -> Optional[float]:
    if start_price is None or end_price is None or start_price <= 0:
        return None
    return (end_price / start_price) - 1.0


def _qualification_basis(raw_qualifies: bool, adjusted_qualifies: bool) -> str:
    if raw_qualifies and adjusted_qualifies:
        return "both"
    if raw_qualifies:
        return "raw"
    return "adjusted"


def _optional_float(value: object) -> Optional[float]:
    if pd.isna(value):
        return None
    return float(value)


def _build_episode(
    windows: Sequence[QualifyingWindow],
    sequence_number: int,
) -> Episode:
    first = windows[0]
    best = max(windows, key=lambda item: item.return_90d or float("-inf"))
    return Episode(
        ticker=first.ticker,
        episode_id=f"{first.ticker}_{sequence_number:03d}",
        company_name=first.company_name,
        exchange=first.exchange,
        first_qualifying_start_date=first.start_date,
        first_qualifying_end_date=first.end_date,
        best_90d_start_date=best.start_date,
        best_90d_end_date=best.end_date,
        best_90d_return=best.return_90d or 0.0,
        episode_start_date=min(window.start_date for window in windows),
        episode_end_date=max(window.end_date for window in windows),
        num_qualifying_windows=len(windows),
        data_quality=first.data_quality,
        preliminary=first.preliminary,
    )


def _write_rows(rows: Sequence[dict], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _fieldnames_for_path(output_path, rows)
    if not rows:
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
        return

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fieldnames_for_path(path: Path, rows: Sequence[dict]) -> list[str]:
    if rows:
        return list(rows[0].keys())
    if "episode" in path.name:
        return EPISODE_COLUMNS
    return WINDOW_COLUMNS
