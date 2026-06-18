"""Simple POC price data providers for M17 sample discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class AkShareProvider:
    """AKShare POC provider for low-cost market data."""

    name: str = "akshare"
    us_hist_disable_after_failures: int = 3
    _us_hist_failures: int = field(default=0, init=False, repr=False)
    _us_hist_disabled: bool = field(default=False, init=False, repr=False)

    def fetch_daily_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        import akshare as ak

        symbol = ticker.strip().upper()
        if symbol.endswith(".HK"):
            return self._fetch_hk(ak, symbol, start_date, end_date)
        if symbol.endswith((".SH", ".SZ", ".BJ")):
            return self._fetch_a_share(ak, symbol, start_date, end_date)
        return self._fetch_us(ak, symbol, start_date, end_date)

    @staticmethod
    def _fetch_a_share(
        ak,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        symbol = ticker.split(".")[0]
        frame = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq",
        )
        return frame if frame is not None else pd.DataFrame()

    @staticmethod
    def _fetch_hk(
        ak,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        symbol = ticker.replace(".HK", "").zfill(5)
        frame = ak.stock_hk_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq",
        )
        return frame if frame is not None else pd.DataFrame()

    def _fetch_us(
        self,
        ak,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        symbol = ticker.replace(".US", "")
        if not self._us_hist_disabled:
            for prefix in ("105.", "106.", ""):
                try:
                    frame = ak.stock_us_hist(
                        symbol=f"{prefix}{symbol}",
                        period="daily",
                        start_date=start_date.strftime("%Y%m%d"),
                        end_date=end_date.strftime("%Y%m%d"),
                        adjust="qfq",
                    )
                except Exception:
                    self._record_us_hist_failure()
                    if self._us_hist_disabled:
                        break
                    continue
                if frame is not None and not frame.empty:
                    self._us_hist_failures = 0
                    return frame
                self._record_us_hist_failure()
                if self._us_hist_disabled:
                    break

        return self._fetch_us_daily(ak, symbol, start_date, end_date)

    @staticmethod
    def _fetch_us_daily(
        ak,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        try:
            frame = ak.stock_us_daily(symbol=symbol, adjust="qfq")
        except TypeError:
            frame = ak.stock_us_daily(symbol=symbol)
        except Exception:
            return pd.DataFrame()
        if frame is None or frame.empty:
            return pd.DataFrame()
        return AkShareProvider._clip_date_range(frame, start_date, end_date)

    def _record_us_hist_failure(self) -> None:
        self._us_hist_failures += 1
        if self._us_hist_failures >= self.us_hist_disable_after_failures:
            self._us_hist_disabled = True

    @staticmethod
    def _clip_date_range(
        frame: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        date_column = None
        for column in frame.columns:
            if str(column).lower() in {"date", "日期"}:
                date_column = column
                break
        if date_column is None:
            return frame
        clipped = frame.copy()
        dates = pd.to_datetime(clipped[date_column], errors="coerce").dt.date
        clipped = clipped[(dates >= start_date) & (dates <= end_date)]
        return clipped.reset_index(drop=True)


class FreeFallbackProvider:
    """Low-cost fallback provider that prefers yfinance, then AKShare."""

    name = "free"

    def __init__(self, yfinance_disable_after_failures: int = 3) -> None:
        self.last_source = ""
        self._providers = (YFinanceProvider(), AkShareProvider())
        self._provider_failures: dict[str, int] = {}
        self._disabled_providers: set[str] = set()
        self._yfinance_disable_after_failures = yfinance_disable_after_failures

    def fetch_daily_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        errors: list[str] = []
        for provider in self._providers:
            if provider.name in self._disabled_providers:
                errors.append(f"{provider.name}: skipped after repeated failures")
                continue
            try:
                frame = provider.fetch_daily_prices(ticker, start_date, end_date)
                if frame is None or frame.empty:
                    raise ValueError("no price data returned")
                self.last_source = provider.name
                self._provider_failures[provider.name] = 0
                return frame
            except Exception as exc:  # noqa: BLE001 - preserve provider-specific errors
                errors.append(f"{provider.name}: {exc}")
                self._record_provider_failure(provider.name)

        self.last_source = ""
        raise RuntimeError("all free sources failed: " + "; ".join(errors))

    def _record_provider_failure(self, provider_name: str) -> None:
        failures = self._provider_failures.get(provider_name, 0) + 1
        self._provider_failures[provider_name] = failures
        if (
            provider_name == "yfinance"
            and failures >= self._yfinance_disable_after_failures
        ):
            self._disabled_providers.add(provider_name)


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
