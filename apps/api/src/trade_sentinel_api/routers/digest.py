from fastapi import APIRouter, Depends, Query

from trade_sentinel_api.models.schemas import DigestToday, ScreenerResult
from trade_sentinel_api.routers.deps.screener import ScreenerFilters, screener_filters_query
from trade_sentinel_api.services.digest import (
    build_digest_today,
    screen_market_universe,
    screen_watchlist,
)

router = APIRouter(tags=["digest"])


@router.get("/digest/today", response_model=DigestToday)
async def digest_today(
    watchlist: str = "default",
    summarize: bool = Query(False),
    refresh: bool = Query(False),
) -> DigestToday:
    return await build_digest_today(watchlist, summarize=summarize, refresh=refresh)


@router.get("/screener/watchlist", response_model=ScreenerResult)
async def screener_watchlist(
    watchlist: str = "default",
    refresh: bool = Query(False),
    filters: ScreenerFilters = Depends(screener_filters_query),
) -> ScreenerResult:
    return await screen_watchlist(
        watchlist_name=watchlist,
        refresh=refresh,
        mos_min=filters.mos_min,
        mos_max=filters.mos_max,
        pe_max=filters.pe_max,
        valuation_label=filters.valuation_label,
        has_earnings_within_days=filters.has_earnings_within_days,
        insider_sentiment=filters.insider_sentiment,
        warning_any=filters.warning_any,
        preset=filters.preset,
    )


@router.get("/screener/market", response_model=ScreenerResult)
async def screener_market(
    universe: str = Query("sp500"),
    refresh: bool = Query(False),
    filters: ScreenerFilters = Depends(screener_filters_query),
) -> ScreenerResult:
    return await screen_market_universe(
        universe=universe,
        refresh=refresh,
        mos_min=filters.mos_min,
        mos_max=filters.mos_max,
        pe_max=filters.pe_max,
        valuation_label=filters.valuation_label,
        has_earnings_within_days=filters.has_earnings_within_days,
        insider_sentiment=filters.insider_sentiment,
        warning_any=filters.warning_any,
        preset=filters.preset,
    )
