from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from trade_sentinel_api.models.schemas.filings import InsiderTransaction


class OptionsExpiryBreakdown(BaseModel):
    expiry: str
    call_volume: float = 0
    put_volume: float = 0
    put_call_ratio: float | None = None
    call_oi: float = 0
    put_oi: float = 0


class OptionsStrikeVolume(BaseModel):
    strike: float
    side: Literal["call", "put"]
    volume: float
    open_interest: float | None = None


class OptionsUnusualContract(BaseModel):
    strike: float
    side: Literal["call", "put"]
    expiry: str
    volume: float
    open_interest: float | None = None
    vol_oi_ratio: float | None = None
    premium_estimate: float | None = None
    is_otm: bool = False
    days_to_expiry: int | None = None
    unusual_opening: bool = False


class OptionsFlowFlag(BaseModel):
    put_call_ratio: float | None = None
    unusual: bool = False
    high_conviction: bool = False
    institutional_grade: bool = False
    conviction_band: Literal["short", "swing", "macro"] | None = None
    premium_total_usd: float | None = None
    message: str | None = None
    call_volume: float | None = None
    put_volume: float | None = None
    expiry: str | None = None
    expiry_breakdown: list[OptionsExpiryBreakdown] = Field(default_factory=list)
    top_strikes: list[OptionsStrikeVolume] = Field(default_factory=list)
    total_open_interest: float | None = None
    open_interest_available: bool = False
    unusual_reason: str | None = None
    unusual_contracts: list[OptionsUnusualContract] = Field(default_factory=list)
    max_vol_oi_ratio: float | None = None
    otm_premium_total: float | None = None
    short_dated_premium_pct: float | None = None
    call_skew_score: float | None = None
    put_skew_score: float | None = None
    data_source: Literal["polygon_ticks", "yfinance_aggregate", "polygon_snapshot"] = "yfinance_aggregate"
    sweep_candidates: list[dict[str, str | float | bool | None]] = Field(default_factory=list)
    aggressive_call_pct: float | None = None
    aggressive_put_pct: float | None = None


class VolumeFootprint(BaseModel):
    current_price: float = 0
    obv_divergence: Literal["bullish", "bearish"] | None = None
    ad_divergence: Literal["bullish", "bearish"] | None = None
    vwap_deviation_pct: float | None = None
    vwap_signal: str | None = None
    volume_ratio: float | None = None
    quiet_accumulation: bool = False
    stance: Literal["accumulation", "distribution", "neutral"] = "neutral"
    analysis_bullets: list[str] = Field(default_factory=list)
    data_available: bool = False
    message: str | None = None


class SmartMoneyLayerScore(BaseModel):
    layer: str
    label: str
    score: float = 0
    max_score: float = 0
    stance: str | None = None
    detail: str | None = None


class SmartMoneyAssessment(BaseModel):
    ticker: str
    conviction_pct: float | None = None
    headline: str | None = None
    layers: list[SmartMoneyLayerScore] = Field(default_factory=list)
    calendar_notes: list[str] = Field(default_factory=list)
    data_available: bool = False


SmartMoneySide = Literal["buy", "sell", "other"]


class SmartMoneyFeedItem(BaseModel):
    ticker: str | None = None
    company_name: str | None = None
    filing_date: str
    insider_name: str | None = None
    title: str | None = None
    transaction_type: str | None = None
    transaction_code: str | None = None
    shares: float | None = None
    price: float | None = None
    notional: float | None = None
    side: SmartMoneySide = "other"
    filing_url: str | None = None
    is_notable: bool = False
    excerpt_available: bool = False
    is_open_market: bool = False
    cluster_buying: bool = False
    source_form: Literal["3", "4", "5"] = "4"
    signal_type: Literal["transaction", "insider_appointment", "annual_reconciliation"] = "transaction"


class SmartMoneyFeedStats(BaseModel):
    buy_count: int = 0
    sell_count: int = 0
    other_count: int = 0
    total_notional: float | None = None
    top_tickers: list[str] = Field(default_factory=list)


class SmartMoneyFeed(BaseModel):
    as_of: datetime
    items: list[SmartMoneyFeedItem] = Field(default_factory=list)
    stats: SmartMoneyFeedStats = Field(default_factory=SmartMoneyFeedStats)
    data_available: bool = False
    message: str | None = None
    days_window: int = 1
    start_date: str | None = None
    end_date: str | None = None
    raw_entry_count: int = 0
    enriched_count: int = 0
    parse_failed_count: int = 0
    xml_attempt_count: int = 0
    filtered_count: int = 0
    sec_rate_limited: bool = False


class WatchlistInsiderPulseRow(BaseModel):
    ticker: str
    sentiment: Literal["accumulation", "distribution", "neutral"] = "neutral"
    net_shares_90d: float = 0
    buy_count: int = 0
    sell_count: int = 0
    open_market_buy_count: int = 0
    cluster_buying: bool = False
    latest_notable: str | None = None
    recent_transactions: list[InsiderTransaction] = Field(default_factory=list)
    data_available: bool = False


class WatchlistInsiderPulse(BaseModel):
    as_of: datetime
    watchlist_name: str = "default"
    rows: list[WatchlistInsiderPulseRow] = Field(default_factory=list)
    data_available: bool = False
    message: str | None = None


class OptionsScanRow(BaseModel):
    ticker: str
    put_call_ratio: float | None = None
    unusual: bool = False
    unusual_reason: str | None = None
    call_volume: float | None = None
    put_volume: float | None = None
    top_strike_summary: str | None = None
    unusual_contract_count: int = 0
    max_vol_oi_ratio: float | None = None
    sweep_count: int = 0
    data_source: str = "yfinance_aggregate"


class OptionsScanResult(BaseModel):
    as_of: datetime
    universe: Literal["watchlist", "sp100", "sp500"] = "sp500"
    rows: list[OptionsScanRow] = Field(default_factory=list)
    scanned_count: int = 0
    fetched_count: int = 0
    data_available: bool = False
    message: str | None = None
    partial: bool = False
    provider_degraded: bool = False
    disclaimer: str = (
        "Heuristic put/call scan via yfinance — not exchange block-flow or paid unusual-activity data."
    )


class VolumeScanRow(BaseModel):
    ticker: str
    stance: Literal["accumulation", "distribution", "neutral"] = "neutral"
    obv_divergence: str | None = None
    ad_divergence: str | None = None
    vwap_deviation_pct: float | None = None
    volume_ratio: float | None = None
    quiet_accumulation: bool = False


class VolumeScanResult(BaseModel):
    as_of: datetime
    universe: Literal["watchlist", "sp100", "sp500"] = "sp500"
    rows: list[VolumeScanRow] = Field(default_factory=list)
    scanned_count: int = 0
    fetched_count: int = 0
    data_available: bool = False
    message: str | None = None
    partial: bool = False
    provider_degraded: bool = False


class ActivistFeedItem(BaseModel):
    ticker: str | None = None
    company_name: str | None = None
    filing_date: str
    form_type: Literal["13D", "13G"] = "13G"
    filer_name: str | None = None
    percent_owned: float | None = None
    is_activist: bool = False
    filing_url: str | None = None
    signal: str | None = None


class ActivistFeed(BaseModel):
    as_of: datetime
    items: list[ActivistFeedItem] = Field(default_factory=list)
    data_available: bool = False
    message: str | None = None
    days_window: int = 30


class Institutional13FChange(BaseModel):
    filer_name: str
    filer_cik: str
    ticker: str
    shares: float | None = None
    value_usd: float | None = None
    change_type: Literal["new", "increased", "decreased", "exit", "held"] = "held"
    prior_shares: float | None = None
    pct_change: float | None = None
    quarter_end: str | None = None
    quarter_note: str | None = None
    is_notable_filer: bool = False


class Institutional13FChanges(BaseModel):
    ticker: str
    as_of: datetime
    changes: list[Institutional13FChange] = Field(default_factory=list)
    notable_filer_changes: list[Institutional13FChange] = Field(default_factory=list)
    conviction_buy: bool = False
    crowding_score: float | None = None
    crowding_risk: Literal["low", "medium", "high"] | None = None
    holder_count: int | None = None
    holder_count_delta: int | None = None
    data_scope: Literal["full_universe", "tracked_filers_only"] = "tracked_filers_only"
    data_available: bool = False
    message: str | None = None
    disclaimer: str = "13F data is quarterly and up to 45 days delayed."


class Institutional13FHolderRow(BaseModel):
    filer_name: str
    filer_cik: str
    shares: float | None = None
    value_usd: float | None = None
    quarter_end: str | None = None
    is_notable_filer: bool = False


class Institutional13FHolders(BaseModel):
    ticker: str
    as_of: datetime
    quarter_end: str | None = None
    holders: list[Institutional13FHolderRow] = Field(default_factory=list)
    holder_count: int = 0
    data_scope: Literal["full_universe", "tracked_filers_only"] = "tracked_filers_only"
    data_available: bool = False
    message: str | None = None


class InstitutionalConvictionRow(BaseModel):
    ticker: str
    filer_count: int = 0
    holder_count: int | None = None
    holder_count_delta: int | None = None
    conviction_buy: bool = False
    top_filers: list[str] = Field(default_factory=list)
    strongest_change: str | None = None
    headline_filer: str | None = None
    headline_pct_change: float | None = None
    headline_value_usd: float | None = None
    quarter_end: str | None = None
    filer_previews: list[dict[str, str | float | None]] = Field(default_factory=list)
    filer_changes: list[Institutional13FChange] = Field(default_factory=list)


class InsiderScanRow(BaseModel):
    ticker: str
    sentiment: Literal["accumulation", "distribution", "neutral"] = "neutral"
    buy_count: int = 0
    sell_count: int = 0
    cluster_buying: bool = False
    notable_buy_count: int = 0
    net_shares_90d: float = 0
    open_market_buy_count: int = 0
    latest_notable: str | None = None
    recent_transactions: list[InsiderTransaction] = Field(default_factory=list)
    data_available: bool = False


class InsiderScanResult(BaseModel):
    as_of: datetime
    universe: Literal["watchlist", "sp100", "sp500"] = "sp500"
    rows: list[InsiderScanRow] = Field(default_factory=list)
    scanned_count: int = 0
    fetched_count: int = 0
    data_available: bool = False
    message: str | None = None
    partial: bool = False
    provider_degraded: bool = False


class InstitutionalConvictionScan(BaseModel):
    as_of: datetime
    universe: Literal["watchlist", "sp100", "sp500"] = "sp500"
    rows: list[InstitutionalConvictionRow] = Field(default_factory=list)
    data_available: bool = False
    message: str | None = None
    filers_refreshed: int = 0
    tickers_mapped: int = 0
    data_scope: Literal["full_universe", "tracked_filers_only"] = "tracked_filers_only"
    disclaimer: str = "13F data is quarterly and up to 45 days delayed after quarter end."


class CotPositionRow(BaseModel):
    symbol: str
    market_name: str | None = None
    report_date: str | None = None
    commercial_net: float | None = None
    signal: str | None = None
    reversal_zone: bool = False


class CotReport(BaseModel):
    as_of: datetime
    positions: list[CotPositionRow] = Field(default_factory=list)
    data_available: bool = False
    message: str | None = None
    disclaimer: str = ""


class FundHoldingRow(BaseModel):
    name: str | None = None
    cusip: str | None = None
    ticker: str | None = None
    asset_category: str | None = None
    fair_value_usd: float | None = None
    pct_of_nav: float | None = None


class FundHoldingsSnapshot(BaseModel):
    fund_ticker: str
    fund_cik: str | None = None
    fund_name: str | None = None
    report_date: str | None = None
    holdings: list[FundHoldingRow] = Field(default_factory=list)
    equity_pct: float | None = None
    fixed_income_pct: float | None = None
    derivatives_pct: float | None = None
    data_available: bool = False
    message: str | None = None


class GammaExposureSnapshot(BaseModel):
    symbol: str
    as_of: datetime
    net_gex_usd: float | None = None
    regime: Literal["positive", "negative", "neutral"] | None = None
    data_source: str = "computed"
    data_available: bool = False
    message: str | None = None


class DixProxySnapshot(BaseModel):
    ticker: str
    as_of: datetime
    short_volume_ratio: float | None = None
    elevated_dark_accumulation: bool = False
    data_source: str = "finra_proxy"
    data_available: bool = False
    message: str | None = None


class MicrostructureSnapshot(BaseModel):
    as_of: datetime
    gex: GammaExposureSnapshot | None = None
    dix: DixProxySnapshot | None = None
    conviction_multiplier: float = 1.0
    notes: list[str] = Field(default_factory=list)


class DarkPoolPrint(BaseModel):
    ticker: str
    trade_date: str
    price: float | None = None
    size: float | None = None
    signature_bullish: bool | None = None
    data_source: str = "proxy"


class DarkPoolSummary(BaseModel):
    ticker: str
    as_of: datetime
    prints: list[DarkPoolPrint] = Field(default_factory=list)
    print_count: int = 0
    bullish_signature_count: int = 0
    data_source: str = "proxy"
    data_available: bool = False
    message: str | None = None


class CongressionalTrade(BaseModel):
    politician: str
    chamber: Literal["house", "senate", "unknown"] = "unknown"
    ticker: str | None = None
    transaction_date: str | None = None
    disclosure_date: str | None = None
    transaction_type: str | None = None
    amount_range: str | None = None
    source_url: str | None = None


class CongressionalFeed(BaseModel):
    as_of: datetime
    trades: list[CongressionalTrade] = Field(default_factory=list)
    days_window: int = 30
    data_source: str = "none"
    data_available: bool = False
    message: str | None = None

