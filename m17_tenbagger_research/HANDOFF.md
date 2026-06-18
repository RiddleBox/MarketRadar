# M17 Ten-Bagger Research Handoff

> Last updated: 2026-06-18
> Module: M17 ten-bagger sample collection
> Current phase: Step 1 sample collection

## Background

M17 is building a US equity sample library for 90-natural-day ten-bagger moves.

The current definition is:

```text
US-listed stocks
scan_start_date = 2015-01-01
scan_end_date = 2025-12-31
window = 90 natural days
qualifies if close return >= 1000%
end_date = first trading day on or after start_date + 90 natural days
```

Price handling is dual-track:

```text
raw_close
adjusted_close
raw_return_90d
adjusted_return_90d
```

Quality tiers:

```text
BOTH_QUALIFIED
RAW_ONLY_REVIEW
ADJUSTED_ONLY_REVIEW
```

Important interpretation:

```text
BOTH_QUALIFIED is the higher-confidence sample layer.
RAW_ONLY_REVIEW often includes corporate-action / reverse-split distortions.
Do not mix RAW_ONLY_REVIEW into the high-confidence ten-bagger sample without review.
```

## Implemented

Core package:

```text
m17_tenbagger_research/
```

Important files:

```text
m17_tenbagger_research/sample_discovery.py
m17_tenbagger_research/schemas.py
m17_tenbagger_research/ticker_universe.py
m17_tenbagger_research/data_providers.py
m17_tenbagger_research/pipeline.py
m17_tenbagger_research/run_small_poc.py
m17_tenbagger_research/run_full_batch.py
m17_tenbagger_research/PROGRESS.md
```

Tests:

```text
tests/test_m17_sample_discovery.py
tests/test_m17_ticker_universe_and_pipeline.py
```

The full-batch runner supports:

```text
OpenD US universe
free low-cost provider: yfinance -> AKShare
batch output
shared price cache
merge-only final output
resume by --start-batch
quota fail-fast
skip quota-exhausted invalid batches during merge
retry quota-failed batches instead of trusting old _DONE.json
```

Low-cost provider details:

```text
provider=free tries yfinance first, then AKShare.
The pipeline records the actual successful source in sample data_source.
Cache sidecars now preserve provider/source metadata for later reruns.
run_small_poc.py supports: free, yfinance, akshare, stooq, opend.
run_full_batch.py supports: opend, free, yfinance, akshare.
For non-OpenD providers, run_full_batch reuses the saved OpenD universe snapshot.
```

## Current Data State

Output root:

```text
data/tenbagger_research/full/opend/
```

Current valid merged outputs:

```text
data/tenbagger_research/full/opend/samples/all_tenbaggers.csv
data/tenbagger_research/full/opend/episodes/episodes.csv
data/tenbagger_research/full/opend/reports/failed_tickers.csv
data/tenbagger_research/full/opend/reports/full_collection_status.md
data/tenbagger_research/full/opend/reports/sample_collection_report.md
```

Current valid merged result:

```text
OpenD universe tickers: 6456
effective covered tickers: 400
valid batches: 2
quota-exhausted / invalid batches: 5
windows: 2078
episodes: 59
failed tickers: 134
```

Quality summary:

```text
BOTH_QUALIFIED: 180 windows
RAW_ONLY_REVIEW: 1870 windows
ADJUSTED_ONLY_REVIEW: 28 windows
Needs manual review: 1898 windows
```

## Critical Blocker

OpenD returned:

```text
历史K线额度不足，请求失败。额度会滚动释放，直至30天后全部释放。
```

This means the OpenD historical K-line quota is exhausted. Continuing to force OpenD will only produce quota failures.

As of 2026-06-18, a low-cost fallback path exists, so the next practical route is to continue collection under a separate output root:

```powershell
python -m m17_tenbagger_research.run_full_batch --provider free --output-dir data/tenbagger_research/full/free --batch-size 100 --max-batches 1 --request-delay 0.2 --no-cache
```

Notes:

```text
yfinance is currently rate-limited in this environment.
AKShare stock_us_daily successfully recovered GME daily history.
AKShare US daily currently provides a single close series, so GME probe rows are RAW_ONLY_REVIEW rather than BOTH_QUALIFIED.
HKD was still missing from both free sources in the probe.
```

Do not treat these batches as valid sample coverage:

```text
data/tenbagger_research/full/opend/batches/batch_0003/
data/tenbagger_research/full/opend/batches/batch_0004/
data/tenbagger_research/full/opend/batches/batch_0005/
data/tenbagger_research/full/opend/batches/batch_0006/
data/tenbagger_research/full/opend/batches/batch_0007/
```

They were created after quota exhaustion. The updated merge logic skips them.

## Verification

Run:

```powershell
python -m pytest tests/test_m17_sample_discovery.py tests/test_m17_ticker_universe_and_pipeline.py -q
```

Expected current result:

```text
16 passed
```

To rebuild current partial merged outputs from valid batches:

```powershell
python -m m17_tenbagger_research.run_full_batch --merge-only --output-dir data/tenbagger_research/full/opend
```

Expected current result:

```text
provider=opend
universe_tickers=6456
windows=2078
episodes=59
failed=134
output_dir=data\tenbagger_research\full\opend
```

## Continue Instructions

If OpenD historical K-line quota has recovered, continue from batch 3:

```powershell
python -m m17_tenbagger_research.run_full_batch --output-dir data/tenbagger_research/full/opend --start-batch 3
```

If quota is still exhausted, do not continue forcing OpenD. Instead, implement or connect an alternative historical daily price source and keep the same `PriceDataProvider` contract:

```text
fetch_daily_prices(ticker, start_date, end_date) -> DataFrame
```

Required output columns after normalization:

```text
date
raw_close
adjusted_close
volume
```

After adding a new provider:

```text
1. Preserve raw / adjusted dual-track returns.
2. Preserve quality_tier.
3. Preserve episode merge rule: same ticker, qualifying start-date gap < 90 days.
4. Run the M17 tests.
5. Run a small POC first: GME / AMC / HKD.
6. Run a 50-200 ticker micro-batch under data/tenbagger_research/full/free.
7. Only then continue full-universe collection in batches.
```

## Suggested Prompt For Next Agent

```text
Please continue M17 ten-bagger sample collection in this repo.

First read:
- m17_tenbagger_research/HANDOFF.md
- m17_tenbagger_research/PROGRESS.md
- m17_tenbagger_research/run_full_batch.py

Current state:
- Full-batch runner exists.
- Current valid OpenD partial output covers 400 tickers, with 2078 windows and 59 episodes.
- OpenD historical K-line quota was exhausted after batch 2.
- Batches 3-7 are quota-exhausted invalid batches and must not be treated as valid coverage.
- Merge-only currently skips quota-exhausted batches.

Your next task:
1. Run the M17 tests.
2. Run merge-only to verify current partial outputs.
3. If continuing without OpenD, use provider=free and a separate output dir.
4. Start with a 50-200 ticker free-provider micro-batch.
5. Keep BOTH_QUALIFIED / RAW_ONLY_REVIEW / ADJUSTED_ONLY_REVIEW separation intact.
6. Treat AKShare-only US rows as review candidates until raw/adjusted handling is audited.
```
