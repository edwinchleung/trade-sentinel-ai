from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SecFilingHighlight(BaseModel):
    form: str
    filing_date: str
    title: str | None = None
    url: str | None = None
    accession: str | None = None
    excerpt: str | None = None
    excerpt_available: bool = False
    excerpt_chars: int | None = None
    event_items: list[str] | None = None


class SecFilingsFeed(BaseModel):
    ticker: str
    filings: list[SecFilingHighlight] = Field(default_factory=list)
    data_available: bool = False
    message: str | None = None


class FilingSummary(BaseModel):
    form: str
    category: str | None = None
    company: str | None = None
    cik: int | str | None = None
    ticker: str | None = None
    filing_date: str | None = None
    filing_url: str | None = None
    accession: str | None = None
    object_type: str | None = None
    rows: list[dict] = Field(default_factory=list)
    text_excerpt: str | None = None
    parse_error: str | None = None


class CurrentFilingsResponse(BaseModel):
    as_of: datetime
    form: str
    count: int = 0
    items: list[FilingSummary] = Field(default_factory=list)
    data_available: bool = True
    message: str | None = None


class NotableInsiderTransaction(BaseModel):
    filing_date: str
    insider_name: str
    transaction_type: str
    shares: float | None = None
    price: float | None = None
    notional: float | None = None
    filing_url: str | None = None
    excerpt: str | None = None
    excerpt_available: bool = False


class InsiderFilingHighlight(BaseModel):
    filing_date: str
    insider_name: str
    transaction_type: str
    excerpt: str | None = None
    excerpt_available: bool = False
    filing_url: str | None = None


class ForwardOutlook(BaseModel):
    next_earnings_date: str | None = None
    days_until_earnings: int | None = None
    analyst_target: float | None = None
    target_upside_pct: float | None = None
    recommendation: str | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    watch_items: list[str] = Field(default_factory=list)
    outlook_bullets: list[str] = Field(default_factory=list)
    data_available: bool = False


class InsiderSummary(BaseModel):
    net_shares_90d: float = 0
    buy_count: int = 0
    sell_count: int = 0
    open_market_buy_count: int = 0
    open_market_sell_count: int = 0
    excluded_count: int = 0
    cluster_buying: bool = False
    sentiment: Literal["accumulation", "distribution", "neutral"] = "neutral"
    notable_transactions: list[NotableInsiderTransaction] = Field(default_factory=list)
    new_insiders_90d: list[dict[str, str | float | None]] = Field(default_factory=list)
    analysis_bullets: list[str] = Field(default_factory=list)
    data_available: bool = False


class InsiderTransaction(BaseModel):
    filing_date: str
    insider_name: str
    title: str | None = None
    transaction_type: str
    shares: float | None = None
    price: float | None = None
    filing_url: str | None = None
    acquired_disposed: str | None = None
    transaction_code: str | None = None
    is_open_market: bool = False
    is_derivative: bool = False
    source_form: Literal["3", "4", "5"] = "4"


class InsiderTimeline(BaseModel):
    ticker: str
    transactions: list[InsiderTransaction] = Field(default_factory=list)
    data_available: bool = True
    message: str | None = None


class SectorContext(BaseModel):
    sector: str | None = None
    industry: str | None = None
    universe: str | None = None
    sector_pe_prior: float | None = None
    pe_vs_sector_prior_pct: float | None = None
    pe_forward_sector_percentile: float | None = None
    mos_sector_percentile: float | None = None
    sector_headline: str | None = None
    sector_bullets: list[str] = Field(default_factory=list)
    peer_count: int = 0
    data_available: bool = False
    message: str | None = None

