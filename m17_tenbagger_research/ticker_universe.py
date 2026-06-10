"""Ticker universe helpers for M17 sample discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

import pandas as pd


SYMBOL_ALIASES = ("ticker", "symbol", "Symbol", "Ticker")
COMPANY_ALIASES = ("company_name", "name", "Name", "Security Name", "security_name")
EXCHANGE_ALIASES = ("exchange", "Exchange", "listing_exchange", "Listing Exchange")


@dataclass(frozen=True)
class TickerInfo:
    ticker: str
    company_name: str = ""
    exchange: str = ""
    source: str = ""
    active: bool = True
    notes: str = ""

    def to_metadata(self) -> dict[str, str]:
        return {
            "company_name": self.company_name,
            "exchange": self.exchange,
            "source": self.source,
            "notes": self.notes,
        }


def normalize_ticker_universe(
    rows: Iterable[dict],
    *,
    source: str = "",
    allowed_exchanges: Optional[Sequence[str]] = None,
) -> list[TickerInfo]:
    """Normalize provider-specific ticker rows into M17 ticker records."""

    allowed = {exchange.upper() for exchange in allowed_exchanges or ()}
    tickers: dict[str, TickerInfo] = {}

    for row in rows:
        ticker = _clean_ticker(_first_value(row, SYMBOL_ALIASES))
        if not ticker:
            continue

        exchange = str(_first_value(row, EXCHANGE_ALIASES) or "").strip().upper()
        if allowed and exchange and exchange not in allowed:
            continue

        company_name = str(_first_value(row, COMPANY_ALIASES) or "").strip()
        tickers[ticker] = TickerInfo(
            ticker=ticker,
            company_name=company_name,
            exchange=exchange,
            source=source,
        )

    return sorted(tickers.values(), key=lambda item: item.ticker)


def load_ticker_universe_csv(
    path: str | Path,
    *,
    source: str = "csv",
    allowed_exchanges: Optional[Sequence[str]] = None,
) -> list[TickerInfo]:
    frame = pd.read_csv(path)
    return normalize_ticker_universe(
        frame.to_dict(orient="records"),
        source=source,
        allowed_exchanges=allowed_exchanges,
    )


def metadata_by_ticker(tickers: Sequence[TickerInfo]) -> dict[str, dict[str, str]]:
    return {ticker.ticker: ticker.to_metadata() for ticker in tickers}


def fetch_opend_us_universe(
    *,
    host: str = "127.0.0.1",
    port: int = 11111,
    allowed_exchange_types: Sequence[str] = ("US_NASDAQ", "US_NYSE", "US_AMEX"),
    common_stock_only: bool = True,
) -> list[TickerInfo]:
    """Fetch a US stock universe from Futu OpenD."""

    try:
        from futu import Market as FutuMarket
        from futu import OpenQuoteContext, RET_OK, SecurityType
    except ImportError as exc:
        raise RuntimeError("futu-api is not installed") from exc

    quote_ctx = OpenQuoteContext(host=host, port=port)
    try:
        ret, frame = quote_ctx.get_stock_basicinfo(
            market=FutuMarket.US,
            stock_type=SecurityType.STOCK,
        )
        if ret != RET_OK or frame is None or frame.empty:
            raise ValueError(f"OpenD get_stock_basicinfo failed: {frame}")

        allowed = set(allowed_exchange_types)
        rows = []
        for _, row in frame.iterrows():
            if bool(row.get("delisting", False)):
                continue
            if str(row.get("suspension", "False")) == "True":
                continue
            exchange_type = str(row.get("exchange_type", ""))
            if allowed and exchange_type not in allowed:
                continue
            ticker = _from_futu_us_code(str(row.get("code", "")))
            if common_stock_only and not _looks_like_common_stock_ticker(ticker):
                continue

            rows.append(
                {
                    "Symbol": ticker,
                    "Security Name": row.get("name", ""),
                    "Exchange": _exchange_from_futu_exchange_type(exchange_type),
                }
            )

        return normalize_ticker_universe(rows, source="opend_us")
    finally:
        quote_ctx.close()


def _first_value(row: dict, aliases: Iterable[str]) -> object:
    lower_lookup = {str(key).lower(): key for key in row.keys()}
    for alias in aliases:
        key = lower_lookup.get(alias.lower())
        if key is not None:
            return row.get(key)
    return None


def _clean_ticker(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    ticker = str(value).strip().upper()
    if not ticker:
        return ""
    return ticker.replace(" ", "")


def _from_futu_us_code(code: str) -> str:
    if code.startswith("US."):
        return code[3:].upper()
    return code.upper()


def _exchange_from_futu_exchange_type(exchange_type: str) -> str:
    exchange_map = {
        "US_NASDAQ": "NASDAQ",
        "US_NYSE": "NYSE",
        "US_AMEX": "AMEX",
    }
    return exchange_map.get(exchange_type, exchange_type)


def _looks_like_common_stock_ticker(ticker: str) -> bool:
    ticker = ticker.upper()
    if not ticker or any(char.isdigit() for char in ticker):
        return False
    special_tokens = (".PR", ".UT", ".WS", ".WT", ".RT", ".U", ".R")
    if any(token in ticker for token in special_tokens):
        return False
    return ticker.replace(".", "").isalpha()
