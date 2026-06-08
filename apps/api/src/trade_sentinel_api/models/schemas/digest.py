from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DigestTickerRow(BaseModel):
    ticker: str
    price: float | None = None
    change_pct: float | None = None
    mos_pct: float | None = None
    mos_label: str | None = None
    fair_value_low: float | None = None
    fair_value_mid: float | None = None
    fair_value_high: float | None = None
    valuation_label: str | None = None
    pe_forward: float | None = None
    sector: str | None = None
    pe_sector_percentile: float | None = None
    top_warning: str | None = None
    earnings_days: int | None = None
    insider_sentiment: str | None = None
    macro_headline: str | None = None
    valuation_confidence: str | None = None
    one_liner: str | None = None


class DigestToday(BaseModel):
    as_of: datetime
    trading_date: str
    watchlist_name: str = "default"
    tickers: list[DigestTickerRow] = Field(default_factory=list)
    empty_message: str | None = None
    digest_max_tickers: int | None = None


class ScreenerRow(DigestTickerRow):
    rank_score: float | None = None


class ScreenerResult(BaseModel):
    as_of: datetime
    universe: Literal["watchlist", "sp100", "sp500"] = "watchlist"
    preset: str | None = None
    scanned_count: int = 0
    rows: list[ScreenerRow] = Field(default_factory=list)
    empty_message: str | None = None
    cached_at: datetime | None = None
    stale: bool = False

