from datetime import date
from pathlib import Path

import pandas as pd

from m17_tenbagger_research.pipeline import (
    CollectionConfig,
    collect_samples,
    fetch_prices_with_cache,
    write_collection_outputs,
)
from m17_tenbagger_research.data_providers import FutuOpenDProvider
from m17_tenbagger_research.ticker_universe import (
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
