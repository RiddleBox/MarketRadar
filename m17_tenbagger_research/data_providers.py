"""Simple POC price data providers for M17 sample discovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import concurrent.futures
from typing import Protocol

import pandas as pd

from .sample_discovery import DATE_ALIASES


class PriceDataProvider(Protocol):
    name: str

    def fetch_daily_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Return daily price data with provider-specific columns."""


@dataclass(frozen=True)
class YFinanceProvider:
    """Yahoo/yfinance POC provider."""

    name: str = "yfinance"

    def fetch_daily_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        import yfinance as yf

        return yf.download(
            ticker,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            auto_adjust=False,
            progress=False,
            threads=False,
        )


@dataclass(frozen=True)
class StooqProvider:
    """Stooq POC provider using daily CSV downloads."""

    name: str = "stooq"
    us_suffix: str = ".us"

    def fetch_daily_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        symbol = ticker.lower()
        if "." not in symbol:
            symbol = f"{symbol}{self.us_suffix}"

        url = (
            "https://stooq.com/q/d/l/"
            f"?s={symbol}&d1={start_date:%Y%m%d}&d2={end_date:%Y%m%d}&i=d"
        )
        frame = pd.read_csv(url)
        date_aliases = {alias.lower() for alias in DATE_ALIASES}
        has_date = any(str(column).lower() in date_aliases for column in frame.columns)
        if not has_date:
            raise ValueError("Stooq did not return OHLC CSV data")
        return frame


@dataclass(frozen=True)
class FutuOpenDProvider:
    """Futu OpenD provider for small POC historical daily K-line pulls."""

    host: str = "127.0.0.1"
    port: int = 11111
    timeout_seconds: int = 30
    max_count: int = 1000
    max_pages: int = 20
    name: str = "opend"

    def fetch_daily_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            self._fetch_daily_prices_inner,
            ticker,
            start_date,
            end_date,
        )
        try:
            return future.result(timeout=self.timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            executor.shutdown(wait=False, cancel_futures=True)
            raise TimeoutError(
                f"OpenD history kline timed out after {self.timeout_seconds}s"
            ) from exc
        finally:
            if future.done():
                executor.shutdown(wait=False, cancel_futures=True)

    def _fetch_daily_prices_inner(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        try:
            from futu import AuType, KLType, OpenQuoteContext
        except ImportError as exc:
            raise RuntimeError("futu-api is not installed") from exc

        quote_ctx = OpenQuoteContext(host=self.host, port=self.port)
        try:
            adjusted = self._request_history_pages(
                quote_ctx,
                self._to_futu_code(ticker),
                start_date,
                end_date,
                KLType,
                AuType.QFQ,
            )
            raw = self._request_history_pages(
                quote_ctx,
                self._to_futu_code(ticker),
                start_date,
                end_date,
                KLType,
                AuType.NONE,
            )
            return self._merge_futu_frames(raw, adjusted)
        finally:
            quote_ctx.close()

    def _request_history_pages(
        self,
        quote_ctx,
        code: str,
        start_date: date,
        end_date: date,
        KLType,
        autype,
    ) -> pd.DataFrame:
        from futu import RET_OK

        frames: list[pd.DataFrame] = []
        page_req_key = None

        for _ in range(self.max_pages):
            ret, frame, page_req_key = quote_ctx.request_history_kline(
                code=code,
                start=start_date.isoformat(),
                end=end_date.isoformat(),
                ktype=KLType.K_DAY,
                autype=autype,
                max_count=self.max_count,
                page_req_key=page_req_key,
            )
            if ret != RET_OK:
                raise ValueError(f"OpenD history kline failed: {frame}")
            if frame is not None and not frame.empty:
                frames.append(frame)
            if page_req_key is None:
                break

        if not frames:
            raise ValueError("OpenD history kline returned no rows")

        return pd.concat(frames, ignore_index=True).drop_duplicates(
            subset=["time_key"], keep="last"
        )

    @staticmethod
    def _to_futu_code(ticker: str) -> str:
        ticker = ticker.strip().upper()
        if ticker.startswith(("US.", "HK.", "SH.", "SZ.")):
            return ticker
        if ticker.endswith(".US"):
            return f"US.{ticker[:-3]}"
        return f"US.{ticker}"

    @staticmethod
    def _normalize_futu_frame(frame: pd.DataFrame) -> pd.DataFrame:
        required = {"time_key", "close"}
        if not required.issubset(set(frame.columns)):
            raise ValueError("OpenD returned K-line data without time_key/close")

        normalized = pd.DataFrame(
            {
                "date": pd.to_datetime(frame["time_key"]).dt.date,
                "raw_close": pd.to_numeric(frame["close"], errors="coerce"),
                "adjusted_close": pd.to_numeric(frame["close"], errors="coerce"),
                "volume": pd.to_numeric(frame.get("volume"), errors="coerce")
                if "volume" in frame.columns
                else pd.NA,
            }
        )
        return normalized

    @classmethod
    def _merge_futu_frames(
        cls,
        raw_frame: pd.DataFrame,
        adjusted_frame: pd.DataFrame,
    ) -> pd.DataFrame:
        raw = cls._normalize_futu_frame(raw_frame)[["date", "raw_close", "volume"]]
        adjusted = cls._normalize_futu_frame(adjusted_frame)[
            ["date", "adjusted_close"]
        ]
        merged = raw.merge(adjusted, on="date", how="outer")
        merged = merged.sort_values("date").reset_index(drop=True)
        return merged[["date", "raw_close", "adjusted_close", "volume"]]
