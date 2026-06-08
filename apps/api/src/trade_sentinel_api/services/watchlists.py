from __future__ import annotations

import hashlib
import logging

from trade_sentinel_api.db import log_storage_backend_once, watchlist_get, watchlist_set
from trade_sentinel_api.models.schemas import Watchlist, WatchlistPatch, WatchlistUpdate
from trade_sentinel_api.services.cache import clear_cached, clear_cached_by_prefix
logger = logging.getLogger(__name__)


def watchlist_ticker_fingerprint(tickers: list[str]) -> str:
    normalized = sorted({t.upper().strip() for t in tickers if t.strip()})
    raw = ",".join(normalized)
    return hashlib.md5(raw.encode()).hexdigest()[:8]


def invalidate_watchlist_caches(watchlist_name: str) -> None:
    """Drop derived caches so digest/screener/smart-money reflect latest tickers."""
    name_upper = watchlist_name.upper()
    clear_cached_by_prefix("digest", name_upper)
    clear_cached_by_prefix("valuation", "")
    clear_cached_by_prefix("smart_money_pulse", name_upper)
    clear_cached_by_prefix("smart_money_options", f"WATCHLIST:{name_upper}")
    if watchlist_name == "default":
        from trade_sentinel_api.services.macro.calendar import macro_trading_date

        trading_day = macro_trading_date()
        clear_cached("macro", f"daily:{trading_day.isoformat()}")
    from trade_sentinel_api.services.scheduler.scheduling import schedule_watchlist_refresh

    schedule_watchlist_refresh(watchlist_name)


def get_watchlist(name: str = "default") -> Watchlist:
    log_storage_backend_once()
    return Watchlist(name=name, tickers=watchlist_get(name))


def update_watchlist(name: str, data: WatchlistUpdate) -> Watchlist:
    previous = watchlist_get(name)
    tickers = watchlist_set(name, data.tickers)
    invalidate_watchlist_caches(name)
    logger.info(
        "watchlist_put name=%s previous_count=%d new_count=%d tickers=%s",
        name,
        len(previous),
        len(tickers),
        tickers,
    )
    return Watchlist(name=name, tickers=tickers)


def patch_watchlist_tickers(name: str, patch: WatchlistPatch) -> Watchlist:
    current = set(watchlist_get(name))
    for raw in patch.remove:
        sym = raw.upper().strip()
        if sym:
            current.discard(sym)
    for raw in patch.add:
        sym = raw.upper().strip()
        if sym:
            current.add(sym)
    tickers = watchlist_set(name, sorted(current))
    invalidate_watchlist_caches(name)
    logger.info(
        "watchlist_patch name=%s new_count=%d added=%s removed=%s tickers=%s",
        name,
        len(tickers),
        [t.upper().strip() for t in patch.add if t.strip()],
        [t.upper().strip() for t in patch.remove if t.strip()],
        tickers,
    )
    return Watchlist(name=name, tickers=tickers)
