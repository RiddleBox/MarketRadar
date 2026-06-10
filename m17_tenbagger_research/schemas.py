"""Data contracts for M17 sample discovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class QualifyingWindow:
    """A 90-natural-day window that meets the ten-bagger threshold."""

    ticker: str
    company_name: str
    exchange: str
    start_date: date
    target_end_date: date
    end_date: date
    raw_start_price: Optional[float]
    raw_end_price: Optional[float]
    raw_return_90d: Optional[float]
    adjusted_start_price: Optional[float]
    adjusted_end_price: Optional[float]
    adjusted_return_90d: Optional[float]
    qualification_basis: str
    data_source: str
    data_quality: str = "POC"
    preliminary: bool = True
    price_basis: str = "dual"
    needs_manual_review: bool = False
    notes: str = ""

    @property
    def return_90d(self) -> Optional[float]:
        returns = [
            value
            for value in (self.raw_return_90d, self.adjusted_return_90d)
            if value is not None
        ]
        return max(returns) if returns else None

    @property
    def quality_tier(self) -> str:
        if self.qualification_basis == "both":
            return "BOTH_QUALIFIED"
        if self.qualification_basis == "raw":
            return "RAW_ONLY_REVIEW"
        if self.qualification_basis == "adjusted":
            return "ADJUSTED_ONLY_REVIEW"
        return "UNKNOWN_REVIEW"

    @property
    def start_price(self) -> Optional[float]:
        if self.qualification_basis == "raw":
            return self.raw_start_price
        if self.adjusted_start_price is not None:
            return self.adjusted_start_price
        return self.raw_start_price

    @property
    def end_price(self) -> Optional[float]:
        if self.qualification_basis == "raw":
            return self.raw_end_price
        if self.adjusted_end_price is not None:
            return self.adjusted_end_price
        return self.raw_end_price

    def to_row(self, episode_id: str = "") -> dict:
        row = empty_window_row()
        row.update(
            {
                "ticker": self.ticker,
                "company_name": self.company_name,
                "exchange": self.exchange,
                "start_date": self.start_date.isoformat(),
                "target_end_date": self.target_end_date.isoformat(),
                "end_date": self.end_date.isoformat(),
                "start_price": self.start_price,
                "end_price": self.end_price,
                "return_90d": self.return_90d,
                "raw_start_price": self.raw_start_price,
                "raw_end_price": self.raw_end_price,
                "raw_return_90d": self.raw_return_90d,
                "adjusted_start_price": self.adjusted_start_price,
                "adjusted_end_price": self.adjusted_end_price,
                "adjusted_return_90d": self.adjusted_return_90d,
                "qualification_basis": self.qualification_basis,
                "quality_tier": self.quality_tier,
                "needs_manual_review": self.needs_manual_review,
                "episode_id": episode_id,
                "data_source": self.data_source,
                "data_quality": self.data_quality,
                "preliminary": self.preliminary,
                "price_basis": self.price_basis,
                "notes": self.notes,
            }
        )
        return row


@dataclass(frozen=True)
class Episode:
    """Merged group of qualifying windows for the same ticker."""

    ticker: str
    episode_id: str
    company_name: str
    exchange: str
    first_qualifying_start_date: date
    first_qualifying_end_date: date
    best_90d_start_date: date
    best_90d_end_date: date
    best_90d_return: float
    episode_start_date: date
    episode_end_date: date
    num_qualifying_windows: int
    data_quality: str = "POC"
    preliminary: bool = True
    notes: str = ""

    def to_row(self) -> dict:
        row = empty_episode_row()
        row.update(
            {
                "ticker": self.ticker,
                "episode_id": self.episode_id,
                "company_name": self.company_name,
                "exchange": self.exchange,
                "first_qualifying_start_date": self.first_qualifying_start_date.isoformat(),
                "first_qualifying_end_date": self.first_qualifying_end_date.isoformat(),
                "best_90d_start_date": self.best_90d_start_date.isoformat(),
                "best_90d_end_date": self.best_90d_end_date.isoformat(),
                "best_90d_return": self.best_90d_return,
                "episode_start_date": self.episode_start_date.isoformat(),
                "episode_end_date": self.episode_end_date.isoformat(),
                "num_qualifying_windows": self.num_qualifying_windows,
                "data_quality": self.data_quality,
                "preliminary": self.preliminary,
                "notes": self.notes,
            }
        )
        return row


WINDOW_COLUMNS = [
    "ticker",
    "company_name",
    "exchange",
    "start_date",
    "target_end_date",
    "end_date",
    "start_price",
    "end_price",
    "return_90d",
    "raw_start_price",
    "raw_end_price",
    "raw_return_90d",
    "adjusted_start_price",
    "adjusted_end_price",
    "adjusted_return_90d",
    "qualification_basis",
    "quality_tier",
    "needs_manual_review",
    "market_cap_at_start",
    "industry",
    "episode_id",
    "data_source",
    "data_quality",
    "preliminary",
    "price_basis",
    "notes",
]

EPISODE_COLUMNS = [
    "ticker",
    "episode_id",
    "company_name",
    "exchange",
    "first_qualifying_start_date",
    "first_qualifying_end_date",
    "best_90d_start_date",
    "best_90d_end_date",
    "best_90d_return",
    "episode_start_date",
    "episode_end_date",
    "num_qualifying_windows",
    "data_quality",
    "preliminary",
    "notes",
]


def empty_window_row() -> dict:
    return {column: "" for column in WINDOW_COLUMNS}


def empty_episode_row() -> dict:
    return {column: "" for column in EPISODE_COLUMNS}
