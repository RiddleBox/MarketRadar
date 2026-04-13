"""Minimal price loader for Task 5 preparation.

Current priority:
1. local CSV
2. future: akshare
3. future: baostock
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

import yaml


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_market_config() -> dict:
    path = CONFIG_DIR / "market_config.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


MARKET_CONFIG = _load_market_config()
CSV_LOCAL_CONFIG = MARKET_CONFIG.get("data_sources", {}).get("csv_local", {})


class PriceLoader:
    """Load historical prices according to market config priority."""

    def load_closes(self, instrument: str, frequency: str = "daily") -> List[float]:
        prices = self._load_from_csv_local(instrument, frequency)
        if prices:
            return prices
        raise FileNotFoundError(f"no price data found for instrument={instrument}, frequency={frequency}")

    def _load_from_csv_local(self, instrument: str, frequency: str) -> List[float]:
        default_directory = CSV_LOCAL_CONFIG.get("default_directory", "data/csv_cache")
        filename_pattern = CSV_LOCAL_CONFIG.get("filename_pattern", "{instrument}_{frequency}.csv")
        csv_path = PROJECT_ROOT / default_directory / filename_pattern.format(instrument=instrument, frequency=frequency)
        if not csv_path.exists():
            return []

        closes: List[float] = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                close = row.get("close")
                if close is None or close == "":
                    continue
                closes.append(float(close))
        return closes
