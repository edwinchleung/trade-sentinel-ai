import asyncio
from datetime import date

from fastapi import APIRouter, Query

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    ActivistFeed,
    CongressionalFeed,
    CotReport,
    DarkPoolSummary,
    FundHoldingsSnapshot,
    InsiderScanResult,
    Institutional13FChanges,
    Institutional13FHolders,
    InstitutionalConvictionScan,
    MicrostructureSnapshot,
    OptionsScanResult,
    SmartMoneyAssessment,
    SmartMoneyFeed,
    VolumeFootprint,
    VolumeScanResult,
    WatchlistInsiderPulse,
)
from trade_sentinel_api.services.congressional_trades import build_congressional_feed
from trade_sentinel_api.services.cot_report import fetch_cot_report
from trade_sentinel_api.services.dark_pool_flow import fetch_dark_pool_summary
from trade_sentinel_api.services.sec.edgar import fetch_insider_timeline, summarize_insider_activity
from trade_sentinel_api.services.microstructure import fetch_microstructure
from trade_sentinel_api.services.options_tick_flow import enrich_options_flow_with_ticks
from trade_sentinel_api.services.sec.form13dg import build_activist_feed, resolve_activist_alert
from trade_sentinel_api.services.sec.form13f import (
    fetch_13f_changes,
    fetch_13f_holders,
    scan_institutional_conviction,
)
from trade_sentinel_api.services.sec.nport import fetch_fund_holdings
from trade_sentinel_api.services.smart_money.assessment import build_smart_money_assessment
from trade_sentinel_api.services.smart_money.feed import build_smart_money_feed
from trade_sentinel_api.services.smart_money.scan import (
    build_watchlist_insider_pulse,
    scan_insider_universe,
    scan_options_universe,
)
from trade_sentinel_api.services.volume import fetch_volume_footprint, scan_volume_universe

router = APIRouter(prefix="/smart-money", tags=["smart-money"])


@router.get("/feed", response_model=SmartMoneyFeed)
async def smart_money_feed(
    days: int | None = Query(None, ge=1),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    side: str = Query("all"),
    form_type: str = Query("4", description="4, 3, 5, or all"),
    notable_only: bool = Query(False),
    min_notional: float | None = Query(None, ge=0),
    open_market_only: bool | None = Query(None),
    cluster_only: bool = Query(False),
    refresh: bool = Query(False),
) -> SmartMoneyFeed:
    settings = get_settings()
    if days is None and start_date is None and end_date is None:
        days = settings.smart_money_feed_default_days
    if days is not None:
        days = min(days, settings.smart_money_feed_max_range_days)
    return await build_smart_money_feed(
        days=days,
        start_date=start_date,
        end_date=end_date,
        side=side,
        form_type=form_type,
        notable_only=notable_only,
        min_notional=min_notional,
        open_market_only=open_market_only,
        cluster_only=cluster_only,
        refresh=refresh,
    )


@router.get("/watchlist-pulse", response_model=WatchlistInsiderPulse)
async def watchlist_insider_pulse(watchlist: str = "default") -> WatchlistInsiderPulse:
    return await build_watchlist_insider_pulse(watchlist)


@router.get("/options-scan", response_model=OptionsScanResult)
async def options_activity_scan(
    universe: str = Query("sp500"),
    watchlist: str = "default",
    signals_only: bool = Query(True),
) -> OptionsScanResult:
    return await scan_options_universe(universe, watchlist, signals_only=signals_only)


@router.get("/insider-scan", response_model=InsiderScanResult)
async def insider_activity_scan(
    universe: str = Query("sp500"),
) -> InsiderScanResult:
    return await scan_insider_universe(universe)


@router.get("/volume-footprint", response_model=VolumeFootprint)
async def volume_footprint(ticker: str = Query(..., min_length=1)) -> VolumeFootprint:
    return await fetch_volume_footprint(ticker.upper())


@router.get("/volume-scan", response_model=VolumeScanResult)
async def volume_scan(
    universe: str = Query("sp500"),
    watchlist: str = "default",
    signals_only: bool = Query(True),
) -> VolumeScanResult:
    return await scan_volume_universe(universe, watchlist, signals_only=signals_only)


@router.get("/activist-feed", response_model=ActivistFeed)
async def activist_feed(
    days: int = Query(30, ge=1, le=90),
    type: str = Query("all", alias="type"),
    refresh: bool = Query(False),
) -> ActivistFeed:
    return await build_activist_feed(days=days, form_filter=type, refresh=refresh)


@router.get("/13f/changes", response_model=Institutional13FChanges)
async def institutional_13f_changes(
    ticker: str = Query(..., min_length=1),
    quarters: int = Query(2, ge=1, le=4),
) -> Institutional13FChanges:
    return await fetch_13f_changes(ticker.upper(), quarters)


@router.get("/13f/holders", response_model=Institutional13FHolders)
async def institutional_13f_holders(
    ticker: str = Query(..., min_length=1),
) -> Institutional13FHolders:
    return await fetch_13f_holders(ticker.upper())


@router.get("/13f/conviction", response_model=InstitutionalConvictionScan)
async def institutional_conviction_scan(
    universe: str = Query("sp500"),
) -> InstitutionalConvictionScan:
    return await scan_institutional_conviction(universe)


@router.get("/nport/{ticker}", response_model=FundHoldingsSnapshot)
async def fund_nport_holdings(ticker: str) -> FundHoldingsSnapshot:
    return await fetch_fund_holdings(ticker.upper())


@router.get("/microstructure/gex", response_model=MicrostructureSnapshot)
async def microstructure_gex(symbol: str = Query("SPY")) -> MicrostructureSnapshot:
    return await fetch_microstructure(symbol.upper())


@router.get("/microstructure/dix-proxy", response_model=MicrostructureSnapshot)
async def microstructure_dix(symbol: str = Query("SPY")) -> MicrostructureSnapshot:
    return await fetch_microstructure(symbol.upper())


@router.get("/dark-pool/{ticker}", response_model=DarkPoolSummary)
async def dark_pool_flow(ticker: str, days: int = Query(5, ge=1, le=30)) -> DarkPoolSummary:
    return await fetch_dark_pool_summary(ticker.upper(), days=days)


@router.get("/congressional-feed", response_model=CongressionalFeed)
async def congressional_feed(
    days: int = Query(30, ge=1, le=365),
    refresh: bool = Query(False),
) -> CongressionalFeed:
    return await build_congressional_feed(days=days, refresh=refresh)


@router.get("/cot", response_model=CotReport)
async def cot_positioning(symbols: str = Query("ES,CL,GC,ZN")) -> CotReport:
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    return await fetch_cot_report(sym_list)


@router.get("/assessment/{ticker}", response_model=SmartMoneyAssessment)
async def smart_money_assessment(ticker: str) -> SmartMoneyAssessment:
    symbol = ticker.upper()
    timeline = await fetch_insider_timeline(symbol)
    insider_summary = (
        summarize_insider_activity(timeline.transactions) if timeline.transactions else None
    )
    options_flow, _ = await enrich_options_flow_with_ticks(symbol)
    volume_fp = await fetch_volume_footprint(symbol)
    changes_13f, activist_alert, fund_holdings, dark_pool, micro = await asyncio.gather(
        fetch_13f_changes(symbol),
        resolve_activist_alert(symbol),
        fetch_fund_holdings(symbol),
        fetch_dark_pool_summary(symbol),
        fetch_microstructure("SPY"),
    )
    return build_smart_money_assessment(
        ticker=symbol,
        insider_summary=insider_summary,
        options_flow=options_flow,
        volume_footprint=volume_fp,
        institutional_conviction=changes_13f.conviction_buy,
        activist_alert=activist_alert,
        crowding_risk=changes_13f.crowding_risk,
        fund_holdings=fund_holdings if fund_holdings.data_available else None,
        dark_pool=dark_pool if dark_pool.data_available else None,
        microstructure=micro,
    )
