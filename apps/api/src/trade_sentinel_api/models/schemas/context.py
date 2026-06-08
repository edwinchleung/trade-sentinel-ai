from datetime import datetime

from pydantic import BaseModel, Field

from trade_sentinel_api.models.schemas.assessment import (
    FundamentalAssessment,
    RealityCheck,
)
from trade_sentinel_api.models.schemas.common import (
    MacdSnapshot,
    NewsDigest,
    NewsItem,
    Warning,
)
from trade_sentinel_api.models.schemas.filings import (
    ForwardOutlook,
    InsiderFilingHighlight,
    InsiderSummary,
    InsiderTimeline,
    SecFilingsFeed,
    SectorContext,
)
from trade_sentinel_api.models.schemas.fundamentals import (
    EarningsSnapshot,
    FundamentalsSnapshot,
)
from trade_sentinel_api.models.schemas.macro import MacroContextOverlay
from trade_sentinel_api.models.schemas.smart_money import (
    ActivistFeedItem,
    Institutional13FChanges,
    OptionsFlowFlag,
    SmartMoneyAssessment,
    VolumeFootprint,
)
from trade_sentinel_api.models.schemas.technical import (
    ContextSummary,
    ContextVisualSnapshot,
    TechnicalAssessment,
)
from trade_sentinel_api.models.schemas.valuation import ValuationAssessment


class TickerContext(BaseModel):
    ticker: str
    as_of: datetime
    price: float | None = None
    change_pct: float | None = None
    market_state: str | None = None
    price_source: str | None = None
    previous_close: float | None = None
    regular_market_price: float | None = None
    extended_price: float | None = None
    is_extended_hours: bool = False
    quote_as_of: str | None = None
    volume: int | None = None
    volume_avg_30d: float | None = None
    volume_ratio: float | None = None
    rsi: float | None = None
    macd: MacdSnapshot | None = None
    news: list[NewsItem] = Field(default_factory=list)
    news_digest: NewsDigest | None = None
    warnings: list[Warning] = Field(default_factory=list)
    fundamental_warnings: list[Warning] = Field(default_factory=list)
    summary: ContextSummary | None = None
    price_history: list[dict] = Field(default_factory=list)
    fundamentals: FundamentalsSnapshot | None = None
    sec_filings: SecFilingsFeed | None = None
    insider: InsiderTimeline | None = None
    insider_summary: InsiderSummary | None = None
    insider_filings: list[InsiderFilingHighlight] = Field(default_factory=list)
    forward_outlook: ForwardOutlook | None = None
    earnings: EarningsSnapshot | None = None
    options_flow: OptionsFlowFlag | None = None
    macro_overlay: MacroContextOverlay | None = None
    valuation: ValuationAssessment | None = None
    technical_assessment: TechnicalAssessment | None = None
    fundamental_assessment: FundamentalAssessment | None = None
    reality_check: RealityCheck | None = None
    sector_context: SectorContext | None = None
    context_visuals: ContextVisualSnapshot | None = None
    volume_footprint: VolumeFootprint | None = None
    smart_money_assessment: SmartMoneyAssessment | None = None
    institutional_13f: "Institutional13FChanges | None" = None
    activist_filing: "ActivistFeedItem | None" = None

