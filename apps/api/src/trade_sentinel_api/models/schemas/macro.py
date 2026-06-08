from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from trade_sentinel_api.models.schemas.common import NewsItem


class MacroSummary(BaseModel):
    bullets: list[str] = Field(default_factory=list)
    model: str
    cached_at: datetime | None = None
    data_gaps: list[str] = Field(default_factory=list)


class MacroEvent(BaseModel):
    name: str
    impact: Literal["high", "moderate", "noise"]
    sectors: list[str] = Field(default_factory=list)
    time_et: str | None = None
    actual: float | None = None
    estimate: float | None = None
    prior: float | None = None
    source: str | None = None
    date: str | None = None
    playbook: str | None = None
    surprise_pct: float | None = None
    beat_miss: Literal["beat", "miss", "inline", "unavailable"] | None = None
    release_status: Literal["released", "scheduled"] | None = None


class MacroSignal(BaseModel):
    symbol: str
    label: str
    level: float | None = None
    change_1d_pct: float | None = None
    change_5d_pct: float | None = None


class FredObservation(BaseModel):
    series_id: str
    label: str
    value: float | None = None
    observation_date: str | None = None


class MacroSignalsSnapshot(BaseModel):
    as_of: datetime
    signals: list[MacroSignal] = Field(default_factory=list)
    yield_curve_10y_3m_bps: float | None = None
    risk_tone: Literal["elevated_vix", "normal", "unavailable"] = "unavailable"
    official: list[FredObservation] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class MacroReleaseStats(BaseModel):
    beats: int = 0
    misses: int = 0
    inline: int = 0
    unavailable: int = 0
    largest_surprises: list[dict] = Field(default_factory=list)


class MacroContextOverlay(BaseModel):
    trading_date: str
    ticker: str | None = None
    ticker_sector: str | None = None
    has_content: bool = False
    market_weather: str | None = None
    signal_highlights: list[str] = Field(default_factory=list)
    headline_events: list[str] = Field(default_factory=list)
    relevant_events: list[MacroEvent] = Field(default_factory=list)
    impact_summary: dict[str, int] = Field(default_factory=dict)
    macro_signals: MacroSignalsSnapshot | None = None
    macro_news: list[NewsItem] = Field(default_factory=list)
    release_stats: MacroReleaseStats | None = None
    data_gaps: list[str] = Field(default_factory=list)


class MacroBriefing(BaseModel):
    as_of: datetime
    market_weather: str | None = None
    events: list[MacroEvent] = Field(default_factory=list)
    headline_events: list[str] = Field(default_factory=list)
    sector_watch: list[str] = Field(default_factory=list)
    watchlist_exposure: list[str] = Field(default_factory=list)
    impact_summary: dict[str, int] = Field(default_factory=dict)
    sector_impacts: list[str] = Field(default_factory=list)
    impact_levels: list[dict] = Field(default_factory=list)
    summary: MacroSummary | None = None
    data_gaps: list[str] = Field(default_factory=list)
    empty_message: str | None = None
    macro_signals: MacroSignalsSnapshot | None = None
    macro_news: list[NewsItem] = Field(default_factory=list)
    signal_highlights: list[str] = Field(default_factory=list)
    release_stats: MacroReleaseStats | None = None
    trading_date: str | None = None

