"""Watchlist digest and screener lite snapshots."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import DigestTickerRow, DigestToday
from trade_sentinel_api.services.cache import clear_cached, get_cached, set_cached_ttl
from trade_sentinel_api.services.digest.cache_keys import (
    _trading_date_key,
    market_screener_cache_key,
)
from trade_sentinel_api.services.digest.lite_rows import (
    _hydrate_digest_rows,
    _lite_row,
    build_lite_row_sync,
    build_lite_rows_batch,
)
from trade_sentinel_api.services.digest.screener import (
    ScreenerFilterParams,
    _build_market_lite_rows,
    apply_screener_filters,
    resolve_screener_filters,
    screen_market_universe,
    screen_watchlist,
)
from trade_sentinel_api.services.macro.context import get_daily_macro_bundle
from trade_sentinel_api.services.scheduler import get_scan_executor
from trade_sentinel_api.services.sector_context import (
    build_sector_context,
    get_sector_universe_stats,
)
from trade_sentinel_api.services.ticker_valuation import (
    resolve_ticker_valuation,
    resolve_ticker_valuation_sync,
    valuation_summary_for_digest,
)
from trade_sentinel_api.services.watchlists import get_watchlist, watchlist_ticker_fingerprint
from trade_sentinel_api.services.yfinance_bundle import (
    earnings_from_bundle,
    fundamentals_from_bundle,
    load_ticker_bundle_sync,
    market_from_bundle,
)

__all__ = [
    "ScreenerFilterParams",
    "_build_market_lite_rows",
    "apply_screener_filters",
    "build_digest_today",
    "build_lite_row_sync",
    "build_lite_rows_batch",
    "clear_cached",
    "earnings_from_bundle",
    "fundamentals_from_bundle",
    "get_cached",
    "get_daily_macro_bundle",
    "get_scan_executor",
    "get_settings",
    "load_ticker_bundle_sync",
    "market_from_bundle",
    "market_screener_cache_key",
    "resolve_screener_filters",
    "resolve_ticker_valuation_sync",
    "screen_market_universe",
    "screen_watchlist",
    "set_cached_ttl",
]


async def build_digest_today(
    watchlist_name: str = "default",
    *,
    summarize: bool = False,
    refresh: bool = False,
    from_background: bool = False,
) -> DigestToday:
    trading_date = _trading_date_key()
    wl = get_watchlist(watchlist_name)
    tickers = [t.upper().strip() for t in wl.tickers if t.strip()][: get_settings().digest_max_tickers]
    fp = watchlist_ticker_fingerprint(wl.tickers)
    cache_key = (
        f"{trading_date}:{watchlist_name}:{'sum' if summarize else 'lite'}:{fp}"
    )
    settings = get_settings()
    cached = get_cached("digest", cache_key)

    if refresh and settings.background_jobs_enabled and not from_background:
        from trade_sentinel_api.services.scheduler.scheduling import schedule_digest_refresh

        schedule_digest_refresh()
        if cached:
            return DigestToday(**cached)
        if not tickers:
            return DigestToday(
                as_of=datetime.now(UTC),
                trading_date=trading_date,
                watchlist_name=watchlist_name,
                empty_message="Watchlist is empty — add tickers to see your daily digest.",
            )
        return DigestToday(
            as_of=datetime.now(UTC),
            trading_date=trading_date,
            watchlist_name=watchlist_name,
            empty_message=(
                "Digest is warming up in the background — refresh in a minute or use Refresh."
            ),
        )

    if refresh:
        clear_cached("digest", cache_key)
        cached = None

    if cached and not refresh:
        return DigestToday(**cached)

    if not tickers:
        return DigestToday(
            as_of=datetime.now(UTC),
            trading_date=trading_date,
            watchlist_name=watchlist_name,
            empty_message="Watchlist is empty — add tickers to see your daily digest.",
        )

    if not refresh and settings.background_jobs_enabled:
        from trade_sentinel_api.services.scheduler.scheduling import schedule_digest_refresh

        schedule_digest_refresh()
        if cached and cached.get("tickers"):
            return DigestToday(**cached)
        return DigestToday(
            as_of=datetime.now(UTC),
            trading_date=trading_date,
            watchlist_name=watchlist_name,
            empty_message=(
                "Digest is warming up in the background — refresh in a minute or use Refresh."
            ),
        )

    if from_background and tickers:
        await build_lite_rows_batch(
            tickers,
            refresh=refresh,
            cache_prefix="digest",
            cache_key=cache_key,
            cache_ttl_seconds=14400,
            max_workers=settings.background_scan_workers,
            include_insider=True,
        )
        cached = get_cached("digest", cache_key)
        if cached and cached.get("tickers"):
            return DigestToday(**cached)
        if cached and cached.get("rows"):
            rows = [DigestTickerRow(**r) for r in cached["rows"]]
            return DigestToday(
                as_of=datetime.now(UTC),
                trading_date=trading_date,
                watchlist_name=watchlist_name,
                tickers=rows,
            )

    macro_bundle = await get_daily_macro_bundle()
    sem = asyncio.Semaphore(get_settings().digest_concurrency)

    async def one(sym: str) -> DigestTickerRow:
        async with sem:
            return await _lite_row(sym, macro_bundle, include_insider=True)

    rows = list(await asyncio.gather(*[one(t) for t in tickers]))
    rows = await _hydrate_digest_rows(rows)

    if summarize:
        from trade_sentinel_api.services.llm import summarize_context

        sector_stats = get_sector_universe_stats("sp500")
        for i, row in enumerate(rows):
            fundamentals, valuation = await resolve_ticker_valuation(row.ticker, price=row.price)
            sector_ctx = build_sector_context(
                row.ticker,
                fundamentals,
                valuation,
                universe="sp500",
                stats=sector_stats,
            )
            facts = {
                "ticker": row.ticker,
                "price": row.price,
                "change_pct": row.change_pct,
                "mos_pct": row.mos_pct,
                "mos_label": row.mos_label,
                "valuation_label": row.valuation_label,
            }
            summary_block = valuation_summary_for_digest(valuation)
            if summary_block:
                facts["valuation_summary"] = summary_block
            if sector_ctx.data_available:
                facts["sector_context"] = sector_ctx.model_dump(mode="json")
            try:
                summary = await summarize_context(facts, prompt_version="v1")
                if summary and summary.bullets:
                    rows[i] = row.model_copy(update={"one_liner": summary.bullets[0]})
            except Exception:
                pass

    digest = DigestToday(
        as_of=datetime.now(UTC),
        trading_date=trading_date,
        watchlist_name=watchlist_name,
        tickers=list(rows),
        digest_max_tickers=get_settings().digest_max_tickers,
    )
    set_cached_ttl("digest", cache_key, digest.model_dump(mode="json"), 14400)
    return digest
