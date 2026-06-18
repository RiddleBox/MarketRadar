"""Run a small M17 Step 1 POC over selected US tickers.

Example:
    python -m m17_tenbagger_research.run_small_poc --provider yfinance GME AMC HKD
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .data_providers import (
    AkShareProvider,
    FreeFallbackProvider,
    FutuOpenDProvider,
    StooqProvider,
    YFinanceProvider,
)
from .pipeline import CollectionConfig, collect_samples, write_collection_outputs
from .ticker_universe import TickerInfo, fetch_opend_us_universe


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M17 small sample POC.")
    parser.add_argument("tickers", nargs="*", help="Tickers to scan, e.g. GME AMC HKD")
    parser.add_argument(
        "--universe",
        choices=("manual", "opend-us"),
        default="manual",
        help="Ticker universe source",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit ticker count for micro-batch POC",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.0,
        help="Delay before each ticker request, useful for OpenD rate limits",
    )
    parser.add_argument(
        "--provider",
        choices=("free", "yfinance", "akshare", "stooq", "opend"),
        default="yfinance",
        help="POC price provider",
    )
    parser.add_argument(
        "--output-dir",
        default="data/tenbagger_research/poc",
        help="Output directory",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable local price cache",
    )
    parser.add_argument(
        "--opend-timeout",
        type=int,
        default=30,
        help="Per-ticker OpenD timeout in seconds",
    )
    args = parser.parse_args()

    if args.provider == "free":
        provider = FreeFallbackProvider()
    elif args.provider == "yfinance":
        provider = YFinanceProvider()
    elif args.provider == "akshare":
        provider = AkShareProvider()
    elif args.provider == "stooq":
        provider = StooqProvider()
    else:
        provider = FutuOpenDProvider(timeout_seconds=args.opend_timeout)
    if args.universe == "opend-us":
        tickers = fetch_opend_us_universe()
    else:
        if not args.tickers:
            parser.error("manual universe requires at least one ticker")
        tickers = [
            TickerInfo(ticker=ticker.upper(), exchange="US", source="manual_poc")
            for ticker in args.tickers
        ]

    if args.limit > 0:
        tickers = tickers[: args.limit]
    config = CollectionConfig(
        scan_start_date=date(2015, 1, 1),
        scan_end_date=date(2025, 12, 31),
        output_dir=Path(args.output_dir) / provider.name,
        use_cache=not args.no_cache,
        request_delay_seconds=args.request_delay,
    )

    result = collect_samples(tickers, provider, config=config)
    paths = write_collection_outputs(
        result,
        output_dir=config.output_dir,
        provider_name=provider.name,
        tickers=tickers,
    )

    print(f"provider={provider.name}")
    print(f"tickers={len(tickers)}")
    print(f"windows={len(result.windows)}")
    print(f"episodes={len(result.episodes)}")
    print(f"failed={len(result.failed_tickers)}")
    for name, path in paths.items():
        print(f"{name}={path}")


if __name__ == "__main__":
    main()
