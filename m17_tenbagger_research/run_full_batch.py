"""Run resumable full-universe M17 Step 1 collection batches."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .data_providers import (
    AkShareProvider,
    FreeFallbackProvider,
    FutuOpenDProvider,
    PriceDataProvider,
    YFinanceProvider,
)
from .pipeline import (
    CollectionConfig,
    CollectionResult,
    collect_samples,
    write_collection_outputs,
    write_failed_tickers_csv,
    write_sample_collection_report,
)
from .sample_discovery import (
    merge_windows_into_episodes,
    write_episodes_csv,
    write_windows_csv,
)
from .schemas import QualifyingWindow
from .ticker_universe import TickerInfo, fetch_opend_us_universe


DEFAULT_OUTPUT_DIR = Path("data/tenbagger_research/full/opend")
DEFAULT_OPEND_UNIVERSE_SNAPSHOT = (
    Path("data/tenbagger_research/full/opend/universe/opend_us.csv")
)
QUOTA_EXHAUSTED_MARKER = "_QUOTA_EXHAUSTED.json"
QUOTA_ERROR_MARKERS = ("额度不足", "额度会滚动释放", "quota", "rate limit", "ratelimit")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run resumable M17 full-universe ten-bagger collection."
    )
    parser.add_argument(
        "--provider",
        choices=("opend", "free", "yfinance", "akshare"),
        default="opend",
        help="Price provider for full collection",
    )
    parser.add_argument(
        "--universe",
        choices=("opend-us",),
        default="opend-us",
        help="Ticker universe source",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Root output directory for full collection",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Tickers per batch",
    )
    parser.add_argument(
        "--start-batch",
        type=int,
        default=1,
        help="1-based batch number to start from",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Maximum number of batches to run in this invocation; 0 means all",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit universe size for a staged run; 0 means full universe",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=1.1,
        help="Delay before each ticker request, useful for provider rate limits",
    )
    parser.add_argument(
        "--opend-timeout",
        type=int,
        default=180,
        help="Per-ticker OpenD timeout in seconds",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable local price cache",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run batches even if their done marker exists",
    )
    parser.add_argument(
        "--merge-only",
        action="store_true",
        help="Only merge existing batch outputs into final CSVs",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    provider = _build_provider(args.provider, opend_timeout=args.opend_timeout)
    tickers = _load_universe_for_mode(
        output_dir,
        args.merge_only,
        provider_name=provider.name,
    )
    if args.limit > 0 and not args.merge_only:
        tickers = tickers[: args.limit]

    if not args.merge_only:
        _write_universe_snapshot(tickers, output_dir / "universe" / "opend_us.csv")
        _run_batches(
            tickers,
            provider,
            output_dir=output_dir,
            batch_size=args.batch_size,
            start_batch=args.start_batch,
            max_batches=args.max_batches,
            request_delay=args.request_delay,
            use_cache=not args.no_cache,
            force=args.force,
        )

    final_result = merge_batch_outputs(output_dir)
    write_collection_outputs(
        final_result,
        output_dir=output_dir,
        provider_name=provider.name,
        tickers=tickers,
    )
    _write_final_report(
        output_dir,
        result=final_result,
        tickers=tickers,
        provider_name=provider.name,
    )

    print(f"provider={provider.name}")
    print(f"universe_tickers={len(tickers)}")
    print(f"windows={len(final_result.windows)}")
    print(f"episodes={len(final_result.episodes)}")
    print(f"failed={len(final_result.failed_tickers)}")
    print(f"output_dir={output_dir}")


def _run_batches(
    tickers: list[TickerInfo],
    provider: PriceDataProvider,
    *,
    output_dir: Path,
    batch_size: int,
    start_batch: int,
    max_batches: int,
    request_delay: float,
    use_cache: bool,
    force: bool,
) -> None:
    config = CollectionConfig(
        scan_start_date=date(2015, 1, 1),
        scan_end_date=date(2025, 12, 31),
        output_dir=output_dir,
        use_cache=use_cache,
        request_delay_seconds=request_delay,
        stop_on_quota_exhaustion=True,
    )
    batches = list(_chunked(tickers, batch_size))
    first_index = max(start_batch - 1, 0)
    last_index = len(batches)
    if max_batches > 0:
        last_index = min(first_index + max_batches, last_index)

    for index in range(first_index, last_index):
        batch_number = index + 1
        batch_tickers = batches[index]
        batch_dir = output_dir / "batches" / f"batch_{batch_number:04d}"
        done_marker = batch_dir / "_DONE.json"
        if done_marker.exists() and not force and not _is_quota_failed_batch(batch_dir):
            print(f"skip batch={batch_number} tickers={len(batch_tickers)}")
            continue
        if done_marker.exists() and _is_quota_failed_batch(batch_dir):
            print(f"retry quota-failed batch={batch_number} tickers={len(batch_tickers)}")

        print(f"run batch={batch_number}/{len(batches)} tickers={len(batch_tickers)}")
        try:
            result = collect_samples(batch_tickers, provider, config=config)
        except Exception as exc:  # noqa: BLE001 - preserve provider error text
            _write_quota_marker(batch_dir, batch_number, batch_tickers, exc)
            raise SystemExit(
                "provider quota appears exhausted; "
                f"stopped before marking batch {batch_number} complete"
            ) from exc
        write_collection_outputs(
            result,
            output_dir=batch_dir,
            provider_name=provider.name,
            tickers=batch_tickers,
        )
        _write_done_marker(done_marker, batch_number, batch_tickers, result)
        print(
            "done "
            f"batch={batch_number} "
            f"windows={len(result.windows)} "
            f"episodes={len(result.episodes)} "
            f"failed={len(result.failed_tickers)}"
        )


def _build_provider(provider_name: str, *, opend_timeout: int) -> PriceDataProvider:
    if provider_name == "free":
        return FreeFallbackProvider()
    if provider_name == "yfinance":
        return YFinanceProvider()
    if provider_name == "akshare":
        return AkShareProvider()
    return FutuOpenDProvider(timeout_seconds=opend_timeout)


def merge_batch_outputs(output_dir: str | Path) -> CollectionResult:
    root = Path(output_dir)
    batch_dirs = sorted((root / "batches").glob("batch_*"))
    valid_batch_dirs = [path for path in batch_dirs if not _is_quota_failed_batch(path)]
    if not valid_batch_dirs:
        raise SystemExit(f"no batch outputs found under {root / 'batches'}")
    windows = _read_batch_windows(valid_batch_dirs)
    episodes = merge_windows_into_episodes(windows)
    failures = _read_batch_failures(valid_batch_dirs)
    return CollectionResult(
        windows=windows,
        episodes=episodes,
        failed_tickers=failures,
    )


def _read_batch_windows(batch_dirs: list[Path]) -> list[QualifyingWindow]:
    windows: list[QualifyingWindow] = []
    for batch_dir in batch_dirs:
        samples_path = batch_dir / "samples" / "all_tenbaggers.csv"
        if not samples_path.exists():
            continue
        frame = pd.read_csv(samples_path)
        if frame.empty:
            continue
        windows.extend(_window_from_row(row) for row in frame.to_dict(orient="records"))
    return sorted(windows, key=lambda item: (item.ticker, item.start_date, item.end_date))


def _read_batch_failures(batch_dirs: list[Path]) -> dict[str, str]:
    failures: dict[str, str] = {}
    for batch_dir in batch_dirs:
        failures_path = batch_dir / "reports" / "failed_tickers.csv"
        if not failures_path.exists():
            continue
        frame = pd.read_csv(failures_path)
        if frame.empty:
            continue
        for row in frame.to_dict(orient="records"):
            ticker = str(row.get("ticker", "")).strip()
            if ticker:
                failures[ticker] = str(row.get("error", ""))
    return dict(sorted(failures.items()))


def _is_quota_failed_batch(batch_dir: Path) -> bool:
    if (batch_dir / QUOTA_EXHAUSTED_MARKER).exists():
        return True
    samples_path = batch_dir / "samples" / "all_tenbaggers.csv"
    failures_path = batch_dir / "reports" / "failed_tickers.csv"
    done_path = batch_dir / "_DONE.json"
    if not failures_path.exists() or not done_path.exists():
        return False

    failures = pd.read_csv(failures_path)
    if failures.empty:
        return False
    samples = pd.read_csv(samples_path) if samples_path.exists() else pd.DataFrame()
    quota_failures = failures["error"].map(_looks_like_quota_error).sum()
    return samples.empty and quota_failures == len(failures)


def _window_from_row(row: dict) -> QualifyingWindow:
    return QualifyingWindow(
        ticker=str(row["ticker"]),
        company_name=_optional_string(row.get("company_name")),
        exchange=_optional_string(row.get("exchange")),
        start_date=_parse_date(row["start_date"]),
        target_end_date=_parse_date(row["target_end_date"]),
        end_date=_parse_date(row["end_date"]),
        raw_start_price=_optional_float(row.get("raw_start_price")),
        raw_end_price=_optional_float(row.get("raw_end_price")),
        raw_return_90d=_optional_float(row.get("raw_return_90d")),
        adjusted_start_price=_optional_float(row.get("adjusted_start_price")),
        adjusted_end_price=_optional_float(row.get("adjusted_end_price")),
        adjusted_return_90d=_optional_float(row.get("adjusted_return_90d")),
        qualification_basis=str(row["qualification_basis"]),
        data_source=_optional_string(row.get("data_source")),
        data_quality=_optional_string(row.get("data_quality")) or "POC",
        preliminary=_optional_bool(row.get("preliminary"), default=True),
        price_basis=_optional_string(row.get("price_basis")) or "dual",
        needs_manual_review=_optional_bool(row.get("needs_manual_review"), default=False),
        notes=_optional_string(row.get("notes")),
    )


def _write_universe_snapshot(tickers: list[TickerInfo], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(ticker) for ticker in tickers]).to_csv(path, index=False)


def _load_universe_for_mode(
    output_dir: Path,
    merge_only: bool,
    *,
    provider_name: str,
) -> list[TickerInfo]:
    if merge_only or provider_name != "opend":
        snapshot_path = _resolve_universe_snapshot(output_dir)
        if snapshot_path is None:
            if merge_only:
                return []
            raise SystemExit(
                "non-OpenD providers need an existing universe snapshot; "
                "expected output_dir/universe/opend_us.csv or "
                f"{DEFAULT_OPEND_UNIVERSE_SNAPSHOT}"
            )
        return _read_universe_snapshot(snapshot_path)
    return fetch_opend_us_universe()


def _resolve_universe_snapshot(output_dir: Path) -> Path | None:
    candidates = [
        output_dir / "universe" / "opend_us.csv",
        DEFAULT_OPEND_UNIVERSE_SNAPSHOT,
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _read_universe_snapshot(snapshot_path: Path) -> list[TickerInfo]:
    frame = pd.read_csv(snapshot_path)
    return [
        TickerInfo(
            ticker=str(row.get("ticker", "")),
            company_name=_optional_string(row.get("company_name")),
            exchange=_optional_string(row.get("exchange")),
            source=_optional_string(row.get("source")),
            active=_optional_bool(row.get("active"), default=True),
            notes=_optional_string(row.get("notes")),
        )
        for row in frame.to_dict(orient="records")
        if _optional_string(row.get("ticker"))
    ]


def _write_done_marker(
    path: Path,
    batch_number: int,
    tickers: list[TickerInfo],
    result: CollectionResult,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch": batch_number,
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "tickers": len(tickers),
        "first_ticker": tickers[0].ticker if tickers else "",
        "last_ticker": tickers[-1].ticker if tickers else "",
        "windows": len(result.windows),
        "episodes": len(result.episodes),
        "failed": len(result.failed_tickers),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_quota_marker(
    batch_dir: Path,
    batch_number: int,
    tickers: list[TickerInfo],
    exc: Exception,
) -> None:
    batch_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch": batch_number,
        "stopped_at": datetime.now().isoformat(timespec="seconds"),
        "tickers": len(tickers),
        "first_ticker": tickers[0].ticker if tickers else "",
        "last_ticker": tickers[-1].ticker if tickers else "",
        "error": str(exc),
    }
    marker_path = batch_dir / QUOTA_EXHAUSTED_MARKER
    marker_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _looks_like_quota_error(value: object) -> bool:
    message = _optional_string(value).lower()
    return any(marker in message for marker in QUOTA_ERROR_MARKERS)


def _write_final_report(
    output_dir: Path,
    *,
    result: CollectionResult,
    tickers: list[TickerInfo],
    provider_name: str,
) -> None:
    report_path = output_dir / "reports" / "full_collection_status.md"
    write_sample_collection_report(
        result,
        report_path,
        provider_name=provider_name,
        tickers=tickers,
    )
    write_windows_csv(
        result.windows,
        output_dir / "samples" / "all_tenbaggers.csv",
        episodes=result.episodes,
    )
    write_episodes_csv(result.episodes, output_dir / "episodes" / "episodes.csv")
    write_failed_tickers_csv(result.failed_tickers, output_dir / "reports" / "failed_tickers.csv")


def _chunked(items: list[TickerInfo], size: int) -> Iterable[list[TickerInfo]]:
    if size <= 0:
        raise ValueError("batch-size must be positive")
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _parse_date(value: object) -> date:
    return pd.to_datetime(value).date()


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value) or value == "":
        return None
    return float(value)


def _optional_string(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _optional_bool(value: object, *, default: bool) -> bool:
    if value is None or pd.isna(value) or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


if __name__ == "__main__":
    main()
