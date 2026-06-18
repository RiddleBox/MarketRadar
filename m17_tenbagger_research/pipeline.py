"""Simple Step 1 collection pipeline for M17."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
from pathlib import Path
import time
from typing import Sequence

import pandas as pd

from .data_providers import PriceDataProvider
from .sample_discovery import normalize_price_frame
from .sample_discovery import (
    merge_windows_into_episodes,
    scan_qualifying_windows,
    write_episodes_csv,
    write_windows_csv,
)
from .schemas import Episode, QualifyingWindow
from .ticker_universe import TickerInfo


@dataclass(frozen=True)
class CollectionConfig:
    scan_start_date: date = date(2015, 1, 1)
    scan_end_date: date = date(2025, 12, 31)
    price_end_buffer_days: int = 100
    output_dir: Path = Path("data/tenbagger_research")
    use_cache: bool = True
    request_delay_seconds: float = 0.0
    stop_on_quota_exhaustion: bool = False

    @property
    def price_end_date(self) -> date:
        return self.scan_end_date + timedelta(days=self.price_end_buffer_days)


@dataclass(frozen=True)
class CollectionResult:
    windows: list[QualifyingWindow]
    episodes: list[Episode]
    failed_tickers: dict[str, str]


def collect_samples(
    tickers: Sequence[TickerInfo],
    provider: PriceDataProvider,
    *,
    config: CollectionConfig = CollectionConfig(),
) -> CollectionResult:
    """Fetch prices for a ticker universe and discover ten-bagger windows."""

    windows: list[QualifyingWindow] = []
    failed_tickers: dict[str, str] = {}

    for ticker_info in tickers:
        try:
            if config.request_delay_seconds > 0:
                time.sleep(config.request_delay_seconds)
            frame = fetch_prices_with_cache(
                provider,
                ticker_info.ticker,
                config=config,
            )
            if not isinstance(frame, pd.DataFrame):
                raise TypeError("provider returned non-DataFrame price data")
            if frame.empty:
                raise ValueError("no price data returned")

            data_source = _provider_source_name(provider)
            windows.extend(
                scan_qualifying_windows(
                    frame,
                    ticker_info.ticker,
                    company_name=ticker_info.company_name,
                    exchange=ticker_info.exchange,
                    data_source=data_source,
                    scan_start_date=config.scan_start_date,
                    scan_end_date=config.scan_end_date,
                )
            )
        except Exception as exc:  # noqa: BLE001 - provider failures must not stop scan
            failed_tickers[ticker_info.ticker] = str(exc)
            if config.stop_on_quota_exhaustion and _is_quota_exhaustion(exc):
                raise

    episodes = merge_windows_into_episodes(windows)
    return CollectionResult(windows=windows, episodes=episodes, failed_tickers=failed_tickers)


def fetch_prices_with_cache(
    provider: PriceDataProvider,
    ticker: str,
    *,
    config: CollectionConfig,
) -> pd.DataFrame:
    """Fetch daily prices and cache normalized provider output locally."""

    cache_path = _price_cache_path(config.output_dir, provider.name, ticker)
    metadata_path = _price_cache_metadata_path(cache_path)
    if config.use_cache and cache_path.exists():
        cached = pd.read_csv(cache_path)
        if not cached.empty:
            _restore_cached_source(provider, metadata_path)
            return cached

    frame = provider.fetch_daily_prices(
        ticker,
        config.scan_start_date,
        config.price_end_date,
    )
    normalized = normalize_price_frame(frame)

    if config.use_cache and not normalized.empty:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(cache_path, index=False)
        metadata = {
            "provider": provider.name,
            "source": _provider_source_name(provider),
        }
        metadata_path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return normalized


def write_collection_outputs(
    result: CollectionResult,
    *,
    output_dir: str | Path,
    provider_name: str = "",
    tickers: Sequence[TickerInfo] = (),
) -> dict[str, Path]:
    """Write Step 1 CSV outputs."""

    root = Path(output_dir)
    samples_path = root / "samples" / "all_tenbaggers.csv"
    episodes_path = root / "episodes" / "episodes.csv"
    report_path = root / "reports" / "sample_collection_report.md"
    failures_path = root / "reports" / "failed_tickers.csv"

    write_windows_csv(result.windows, samples_path, episodes=result.episodes)
    write_episodes_csv(result.episodes, episodes_path)
    write_failed_tickers_csv(result.failed_tickers, failures_path)
    write_sample_collection_report(
        result,
        report_path,
        provider_name=provider_name,
        tickers=tickers,
    )

    return {
        "samples": samples_path,
        "episodes": episodes_path,
        "report": report_path,
        "failures": failures_path,
    }


def write_failed_tickers_csv(failed_tickers: dict[str, str], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"ticker": ticker, "error": error}
        for ticker, error in sorted(failed_tickers.items())
    ]
    if not rows:
        output_path.write_text("ticker,error\n", encoding="utf-8")
        return
    pd.DataFrame(rows).to_csv(output_path, index=False)


def write_sample_collection_report(
    result: CollectionResult,
    path: str | Path,
    *,
    provider_name: str = "",
    tickers: Sequence[TickerInfo] = (),
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# M17 Sample Collection Report",
        "",
        "## Summary",
        "",
        f"- Provider: {provider_name or 'unknown'}",
        f"- Tickers requested: {len(tickers)}",
        f"- Qualifying windows: {len(result.windows)}",
        f"- Episodes: {len(result.episodes)}",
        f"- Failed tickers: {len(result.failed_tickers)}",
        f"- Data quality: POC",
        f"- Preliminary: true",
        "",
        "## Qualification Quality",
        "",
        *[
            f"- {name}: {count}"
            for name, count in _qualification_summary(result.windows).items()
        ],
        *[
            f"- {name}: {count}"
            for name, count in _quality_tier_summary(result.windows).items()
        ],
        f"- Needs manual review: {_manual_review_count(result.windows)}",
        "",
        "## Known Limitations",
        "",
        "- POC data may have survivorship bias.",
        "- Delisted, renamed, merged, or bankrupt securities may be missing.",
        "- Raw and adjusted close conflicts require manual review.",
        "- Provider-specific corporate action handling has not been fully audited.",
        "",
        "## Episodes",
        "",
    ]

    if result.episodes:
        for episode in result.episodes:
            lines.append(
                "- "
                f"{episode.episode_id}: {episode.first_qualifying_start_date} "
                f"to {episode.first_qualifying_end_date}, "
                f"best_return={episode.best_90d_return:.4f}, "
                f"windows={episode.num_qualifying_windows}"
            )
    else:
        lines.append("- No qualifying episodes found.")

    if result.failed_tickers:
        lines.extend(["", "## Failed Tickers", ""])
        for ticker, error in sorted(result.failed_tickers.items()):
            lines.append(f"- {ticker}: {error}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _price_cache_path(output_dir: Path, provider_name: str, ticker: str) -> Path:
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    return Path(output_dir) / "prices" / provider_name / f"{safe_ticker}.csv"


def _price_cache_metadata_path(cache_path: Path) -> Path:
    return cache_path.with_name(f"{cache_path.name}.meta.json")


def _provider_source_name(provider: PriceDataProvider) -> str:
    source_name = getattr(provider, "last_source", "") or provider.name
    return str(source_name)


def _restore_cached_source(
    provider: PriceDataProvider,
    metadata_path: Path,
) -> None:
    source_name = provider.name
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            source_name = str(metadata.get("source") or source_name)
        except json.JSONDecodeError:
            source_name = provider.name

    try:
        setattr(provider, "last_source", source_name)
    except Exception:
        pass


def _qualification_summary(windows: Sequence[QualifyingWindow]) -> dict[str, int]:
    summary = {"both": 0, "raw": 0, "adjusted": 0}
    for window in windows:
        summary[window.qualification_basis] = (
            summary.get(window.qualification_basis, 0) + 1
        )
    return summary


def _manual_review_count(windows: Sequence[QualifyingWindow]) -> int:
    return sum(1 for window in windows if window.needs_manual_review)


def _quality_tier_summary(windows: Sequence[QualifyingWindow]) -> dict[str, int]:
    summary = {
        "BOTH_QUALIFIED": 0,
        "RAW_ONLY_REVIEW": 0,
        "ADJUSTED_ONLY_REVIEW": 0,
    }
    for window in windows:
        summary[window.quality_tier] = summary.get(window.quality_tier, 0) + 1
    return summary


def _is_quota_exhaustion(exc: Exception) -> bool:
    message = str(exc).lower()
    quota_markers = (
        "quota",
        "rate limit",
        "ratelimit",
        "额度不足",
        "额度会滚动释放",
    )
    return any(marker in message for marker in quota_markers)
