from datetime import date
from pathlib import Path
import time

import pandas as pd

from m17_tenbagger_research import data_providers
from m17_tenbagger_research.pipeline import (
    CollectionConfig,
    collect_samples,
    fetch_prices_with_cache,
    write_collection_outputs,
)
from m17_tenbagger_research.data_providers import FutuOpenDProvider
from m17_tenbagger_research.ticker_universe import (
    TickerInfo,
    _exchange_from_futu_exchange_type,
    _from_futu_us_code,
    _looks_like_common_stock_ticker,
    metadata_by_ticker,
    normalize_ticker_universe,
)


class FakeProvider:
    name = "fake"

    def __init__(self, frames):
        self.frames = frames
        self.requests = []

    def fetch_daily_prices(self, ticker, start_date, end_date):
        self.requests.append((ticker, start_date, end_date))
        if ticker == "FAIL":
            raise RuntimeError("boom")
        return self.frames.get(ticker, pd.DataFrame())


class SourceAwareProvider:
    name = "free"

    def __init__(self, frame):
        self.frame = frame
        self.last_source = ""
        self.requests = []

    def fetch_daily_prices(self, ticker, start_date, end_date):
        self.requests.append((ticker, start_date, end_date))
        self.last_source = "akshare"
        return self.frame


def test_normalize_ticker_universe_filters_exchanges_and_dedupes():
    rows = [
        {"Symbol": "aaa", "Security Name": "AAA Corp", "Exchange": "NASDAQ"},
        {"Symbol": "AAA", "Security Name": "AAA Duplicate", "Exchange": "NASDAQ"},
        {"Symbol": "bbb", "Security Name": "BBB Corp", "Exchange": "NYSE"},
        {"Symbol": "otc", "Security Name": "OTC Corp", "Exchange": "OTC"},
    ]

    tickers = normalize_ticker_universe(
        rows,
        source="synthetic",
        allowed_exchanges=("NASDAQ", "NYSE", "AMEX"),
    )

    assert [item.ticker for item in tickers] == ["AAA", "BBB"]
    assert tickers[0].company_name == "AAA Duplicate"
    assert metadata_by_ticker(tickers)["BBB"]["exchange"] == "NYSE"


def test_collect_samples_fetches_provider_and_records_failures(tmp_path):
    tickers = normalize_ticker_universe(
        [
            {"Symbol": "AAA", "Security Name": "AAA Corp", "Exchange": "NASDAQ"},
            {"Symbol": "FAIL", "Security Name": "Fail Corp", "Exchange": "NYSE"},
        ],
        source="synthetic",
    )
    provider = FakeProvider(
        {
            "AAA": pd.DataFrame(
                [
                    {"date": "2021-01-01", "close": 1.0, "adj_close": 1.0},
                    {"date": "2021-04-01", "close": 11.0, "adj_close": 11.0},
                ]
            )
        }
    )

    result = collect_samples(
        tickers,
        provider,
        config=CollectionConfig(
            scan_start_date=date(2021, 1, 1),
            scan_end_date=date(2021, 12, 31),
            output_dir=tmp_path,
        ),
    )

    assert [window.ticker for window in result.windows] == ["AAA"]
    assert len(result.episodes) == 1
    assert result.failed_tickers == {"FAIL": "boom"}
    assert provider.requests[0][0] == "AAA"
    assert provider.requests[0][2] == date(2022, 4, 10)


def test_fetch_prices_with_cache_reuses_normalized_csv(tmp_path):
    provider = FakeProvider(
        {
            "AAA": pd.DataFrame(
                [
                    {"date": "2021-01-01", "close": 1.0, "adj_close": 1.0},
                    {"date": "2021-04-01", "close": 11.0, "adj_close": 11.0},
                ]
            )
        }
    )
    config = CollectionConfig(
        scan_start_date=date(2021, 1, 1),
        scan_end_date=date(2021, 12, 31),
        output_dir=tmp_path,
        use_cache=True,
    )

    first = fetch_prices_with_cache(provider, "AAA", config=config)
    second = fetch_prices_with_cache(provider, "AAA", config=config)

    assert len(provider.requests) == 1
    assert list(first.columns) == ["date", "raw_close", "adjusted_close", "volume"]
    assert list(second.columns) == ["date", "raw_close", "adjusted_close", "volume"]
    assert Path(tmp_path / "prices" / "fake" / "AAA.csv").exists()


def test_fetch_prices_with_cache_restores_cached_source(tmp_path):
    provider = SourceAwareProvider(
        pd.DataFrame(
            [
                {"date": "2021-01-01", "close": 1.0, "adj_close": 1.0},
                {"date": "2021-04-01", "close": 11.0, "adj_close": 11.0},
            ]
        )
    )
    config = CollectionConfig(
        scan_start_date=date(2021, 1, 1),
        scan_end_date=date(2021, 12, 31),
        output_dir=tmp_path,
        use_cache=True,
    )

    fetch_prices_with_cache(provider, "AAA", config=config)
    provider.last_source = ""
    fetch_prices_with_cache(provider, "AAA", config=config)

    assert len(provider.requests) == 1
    assert provider.last_source == "akshare"


def test_free_fallback_provider_records_actual_successful_source(
    monkeypatch,
    tmp_path,
):
    class FakeYFinanceProvider:
        name = "yfinance"

        def fetch_daily_prices(self, ticker, start_date, end_date):
            raise RuntimeError("yf unavailable")

    class FakeAkShareProvider:
        name = "akshare"

        def fetch_daily_prices(self, ticker, start_date, end_date):
            return pd.DataFrame(
                [
                    {"date": "2021-01-01", "close": 1.0, "adj_close": 1.0},
                    {"date": "2021-04-01", "close": 11.0, "adj_close": 11.0},
                ]
            )

    monkeypatch.setattr(data_providers, "YFinanceProvider", FakeYFinanceProvider)
    monkeypatch.setattr(data_providers, "AkShareProvider", FakeAkShareProvider)

    provider = data_providers.FreeFallbackProvider()
    result = collect_samples(
        [TickerInfo(ticker="AAA", company_name="AAA Corp", exchange="NASDAQ")],
        provider,
        config=CollectionConfig(
            scan_start_date=date(2021, 1, 1),
            scan_end_date=date(2021, 12, 31),
            output_dir=tmp_path,
            use_cache=False,
        ),
    )

    assert provider.last_source == "akshare"
    assert [window.data_source for window in result.windows] == ["akshare"]


def test_free_fallback_provider_skips_yfinance_after_repeated_failures(monkeypatch):
    calls = {"yfinance": 0, "akshare": 0}

    class FakeYFinanceProvider:
        name = "yfinance"

        def fetch_daily_prices(self, ticker, start_date, end_date):
            calls["yfinance"] += 1
            raise RuntimeError("rate limited")

    class FakeAkShareProvider:
        name = "akshare"

        def fetch_daily_prices(self, ticker, start_date, end_date):
            calls["akshare"] += 1
            raise RuntimeError("missing")

    monkeypatch.setattr(data_providers, "YFinanceProvider", FakeYFinanceProvider)
    monkeypatch.setattr(data_providers, "AkShareProvider", FakeAkShareProvider)

    provider = data_providers.FreeFallbackProvider(yfinance_disable_after_failures=2)
    for ticker in ("AAA", "BBB", "CCC"):
        try:
            provider.fetch_daily_prices(ticker, date(2021, 1, 1), date(2021, 12, 31))
        except RuntimeError:
            pass

    assert calls == {"yfinance": 2, "akshare": 3}


def test_provider_timeout_helper_raises_timeout():
    try:
        data_providers._call_with_timeout(
            lambda: time.sleep(0.2),
            timeout_seconds=0.01,
            label="slow provider",
        )
    except TimeoutError as exc:
        assert "slow provider timed out" in str(exc)
    else:
        raise AssertionError("expected provider timeout")


def test_akshare_us_provider_falls_back_to_daily_and_clips_dates():
    class FakeAk:
        def stock_us_hist(self, **kwargs):
            raise RuntimeError("proxy unavailable")

        def stock_us_daily(self, **kwargs):
            return pd.DataFrame(
                [
                    {"date": "2020-01-01", "close": 1.0, "volume": 10},
                    {"date": "2021-01-01", "close": 2.0, "volume": 20},
                    {"date": "2022-01-01", "close": 3.0, "volume": 30},
                ]
            )

    frame = data_providers.AkShareProvider()._fetch_us(
        FakeAk(),
        "GME",
        date(2021, 1, 1),
        date(2021, 12, 31),
    )

    assert list(frame["date"]) == ["2021-01-01"]
    assert list(frame["close"]) == [2.0]


def test_akshare_us_provider_skips_hist_after_repeated_failures():
    class FakeAk:
        def __init__(self):
            self.hist_calls = 0
            self.daily_calls = 0

        def stock_us_hist(self, **kwargs):
            self.hist_calls += 1
            raise RuntimeError("proxy unavailable")

        def stock_us_daily(self, **kwargs):
            self.daily_calls += 1
            return pd.DataFrame(
                [{"date": "2021-01-01", "close": 2.0, "volume": 20}]
            )

    fake_ak = FakeAk()
    provider = data_providers.AkShareProvider(us_hist_disable_after_failures=2)

    provider._fetch_us(fake_ak, "GME", date(2021, 1, 1), date(2021, 12, 31))
    provider._fetch_us(fake_ak, "AMC", date(2021, 1, 1), date(2021, 12, 31))

    assert fake_ak.hist_calls == 2
    assert fake_ak.daily_calls == 2


def test_write_collection_outputs_creates_report_and_csvs(tmp_path):
    tickers = normalize_ticker_universe(
        [{"Symbol": "AAA", "Security Name": "AAA Corp", "Exchange": "NASDAQ"}],
        source="synthetic",
    )
    provider = FakeProvider(
        {
            "AAA": pd.DataFrame(
                [
                    {"date": "2021-01-01", "close": 1.0, "adj_close": 1.0},
                    {"date": "2021-04-01", "close": 11.0, "adj_close": 11.0},
                ]
            )
        }
    )
    result = collect_samples(
        tickers,
        provider,
        config=CollectionConfig(
            scan_start_date=date(2021, 1, 1),
            scan_end_date=date(2021, 12, 31),
            output_dir=tmp_path,
        ),
    )

    paths = write_collection_outputs(
        result,
        output_dir=tmp_path,
        provider_name="fake",
        tickers=tickers,
    )

    assert paths["samples"].exists()
    assert paths["episodes"].exists()
    assert paths["failures"].exists()
    report = paths["report"].read_text(encoding="utf-8")
    assert "M17 Sample Collection Report" in report
    assert "AAA_001" in report


def test_write_collection_outputs_writes_headers_for_empty_results(tmp_path):
    result = collect_samples(
        [],
        FakeProvider({}),
        config=CollectionConfig(output_dir=tmp_path),
    )

    paths = write_collection_outputs(result, output_dir=tmp_path, provider_name="fake")

    samples_header = paths["samples"].read_text(encoding="utf-8").splitlines()[0]
    episodes_header = paths["episodes"].read_text(encoding="utf-8").splitlines()[0]
    assert "ticker" in samples_header
    assert "return_90d" in samples_header
    assert "quality_tier" in samples_header
    assert "episode_id" in episodes_header


def test_futu_opend_provider_normalizes_daily_kline_frame():
    frame = pd.DataFrame(
        [
            {"time_key": "2021-01-01 00:00:00", "close": "1.0", "volume": "100"},
            {"time_key": "2021-04-01 00:00:00", "close": "11.0", "volume": "200"},
        ]
    )

    normalized = FutuOpenDProvider._normalize_futu_frame(frame)

    assert list(normalized.columns) == ["date", "raw_close", "adjusted_close", "volume"]
    assert normalized.iloc[0]["raw_close"] == 1.0
    assert normalized.iloc[1]["adjusted_close"] == 11.0
    assert normalized.iloc[1]["volume"] == 200


def test_futu_opend_provider_converts_us_tickers():
    assert FutuOpenDProvider._to_futu_code("GME") == "US.GME"
    assert FutuOpenDProvider._to_futu_code("GME.US") == "US.GME"
    assert FutuOpenDProvider._to_futu_code("US.GME") == "US.GME"


def test_opend_universe_helpers_convert_codes_and_exchanges():
    assert _from_futu_us_code("US.GME") == "GME"
    assert _from_futu_us_code("AAPL") == "AAPL"
    assert _exchange_from_futu_exchange_type("US_NASDAQ") == "NASDAQ"
    assert _exchange_from_futu_exchange_type("US_NYSE") == "NYSE"
    assert _exchange_from_futu_exchange_type("US_AMEX") == "AMEX"


def test_common_stock_ticker_filter_rejects_special_codes():
    assert _looks_like_common_stock_ticker("AAPL") is True
    assert _looks_like_common_stock_ticker("BRK.B") is True
    assert _looks_like_common_stock_ticker("AAIC.PRB") is False
    assert _looks_like_common_stock_ticker("AACBU") is True
    assert _looks_like_common_stock_ticker("2618996D") is False
    assert _looks_like_common_stock_ticker("AAM.UT") is False
