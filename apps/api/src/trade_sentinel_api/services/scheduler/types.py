"""Background job names and metadata."""

from __future__ import annotations

from enum import Enum
from typing import Any

_batch_context: dict[str, Any] = {"position": 0, "total": 0, "reason": ""}


class BackgroundJobName(str, Enum):
    DIGEST = "digest"
    MARKET_SCREENER = "market_screener"
    SMART_MONEY_FEED = "smart_money_feed"
    WATCHLIST_PULSE = "watchlist_pulse"
    OPTIONS_WATCHLIST = "options_watchlist"
    OPTIONS_SP100 = "options_sp100"
    OPTIONS_SP500 = "options_sp500"
    VOLUME_WATCHLIST = "volume_watchlist"
    VOLUME_SP100 = "volume_sp100"
    VOLUME_SP500 = "volume_sp500"
    INSIDER_SP500 = "insider_sp500"
    INSTITUTIONAL_CONVICTION = "institutional_conviction"
    ACTIVIST_FEED = "activist_feed"
    COT_MACRO = "cot_macro"
    EDGAR_REGISTRY_WARM = "edgar_registry_warm"
    SEC_13F_BULK_INGEST = "sec_13f_bulk_ingest"
    SEC_NPORT_BULK_INGEST = "sec_nport_bulk_ingest"
    CONGRESSIONAL_TRADES = "congressional_trades_sync"
    FINRA_SHORT_VOLUME = "finra_short_volume_sync"
    GEX_SNAPSHOT = "gex_snapshot"


JOB_META: dict[str, dict[str, str]] = {
    BackgroundJobName.DIGEST.value: {
        "label": "Daily digest",
        "description": "Building watchlist digest rows",
    },
    BackgroundJobName.MARKET_SCREENER.value: {
        "label": "Market screener",
        "description": "Scanning universe for valuation signals",
    },
    BackgroundJobName.SMART_MONEY_FEED.value: {
        "label": "Insider feed",
        "description": "Fetching SEC Form 4 filings",
    },
    BackgroundJobName.WATCHLIST_PULSE.value: {
        "label": "Watchlist insider pulse",
        "description": "Aggregating watchlist insider activity",
    },
    BackgroundJobName.OPTIONS_WATCHLIST.value: {
        "label": "Options scan (watchlist)",
        "description": "Scanning watchlist for unusual options",
    },
    BackgroundJobName.OPTIONS_SP100.value: {
        "label": "Options scan (S&P 100)",
        "description": "Scanning S&P 100 for unusual options",
    },
    BackgroundJobName.OPTIONS_SP500.value: {
        "label": "Options scan (S&P 500)",
        "description": "Scanning S&P 500 for unusual options",
    },
    BackgroundJobName.VOLUME_WATCHLIST.value: {
        "label": "Volume scan (watchlist)",
        "description": "Scanning watchlist for volume footprints",
    },
    BackgroundJobName.VOLUME_SP100.value: {
        "label": "Volume scan (S&P 100)",
        "description": "Scanning S&P 100 for volume footprints",
    },
    BackgroundJobName.VOLUME_SP500.value: {
        "label": "Volume scan (S&P 500)",
        "description": "Scanning S&P 500 for volume footprints",
    },
    BackgroundJobName.INSIDER_SP500.value: {
        "label": "Insider scan (S&P 500)",
        "description": "Ranking insider accumulation candidates",
    },
    BackgroundJobName.INSTITUTIONAL_CONVICTION.value: {
        "label": "13F institutional conviction",
        "description": "Scanning institutional holdings changes",
    },
    BackgroundJobName.ACTIVIST_FEED.value: {
        "label": "Activist feed",
        "description": "Fetching 13D/G activist filings",
    },
    BackgroundJobName.COT_MACRO.value: {
        "label": "COT macro report",
        "description": "Fetching CFTC commitment of traders data",
    },
    BackgroundJobName.EDGAR_REGISTRY_WARM.value: {
        "label": "Edgar registry warm",
        "description": "Prefetching current filings for registry forms",
    },
    BackgroundJobName.SEC_13F_BULK_INGEST.value: {
        "label": "13F bulk ingest",
        "description": "Ingesting SEC bulk 13F dataset into local index",
    },
    BackgroundJobName.SEC_NPORT_BULK_INGEST.value: {
        "label": "N-PORT bulk ingest",
        "description": "Ingesting SEC N-PORT fund holdings",
    },
    BackgroundJobName.CONGRESSIONAL_TRADES.value: {
        "label": "Congressional trades",
        "description": "Syncing STOCK Act trade disclosures",
    },
    BackgroundJobName.FINRA_SHORT_VOLUME.value: {
        "label": "FINRA short volume",
        "description": "Syncing FINRA short-volume for DIX proxy",
    },
    BackgroundJobName.GEX_SNAPSHOT.value: {
        "label": "GEX snapshot",
        "description": "Computing gamma exposure snapshot",
    },
}


EDGAR_HEAVY_JOBS = frozenset(
    {
        BackgroundJobName.SMART_MONEY_FEED,
        BackgroundJobName.WATCHLIST_PULSE,
        BackgroundJobName.INSIDER_SP500,
        BackgroundJobName.INSTITUTIONAL_CONVICTION,
        BackgroundJobName.ACTIVIST_FEED,
        BackgroundJobName.EDGAR_REGISTRY_WARM,
    }
)

YFINANCE_SCAN_JOBS = frozenset(
    {
        BackgroundJobName.OPTIONS_WATCHLIST,
        BackgroundJobName.OPTIONS_SP100,
        BackgroundJobName.OPTIONS_SP500,
        BackgroundJobName.VOLUME_WATCHLIST,
        BackgroundJobName.VOLUME_SP100,
        BackgroundJobName.VOLUME_SP500,
    }
)


def get_batch_context() -> dict[str, Any]:
    return dict(_batch_context)


def set_batch_context(**kwargs: Any) -> None:
    _batch_context.update(kwargs)
