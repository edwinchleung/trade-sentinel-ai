"""Chunked universe scanning for proactive smart-money jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.services.cache import clear_cached, get_cached, set_cached_ttl
from trade_sentinel_api.services.universe import load_universe_tickers
from trade_sentinel_api.services.watchlists import get_watchlist, watchlist_ticker_fingerprint
from trade_sentinel_api.services.yfinance_bundle import _chunk_symbols

T = TypeVar("T")
R = TypeVar("R", bound=BaseModel)


def resolve_scan_universe(
    universe: str,
    *,
    watchlist_name: str = "default",
) -> tuple[str, list[str], str]:
    """Return (universe_key, tickers, cache_key_suffix)."""
    key = (universe or "sp500").strip().lower()
    if key == "watchlist":
        wl = get_watchlist(watchlist_name)
        tickers = [t.upper().strip() for t in wl.tickers if t.strip()][
            : get_settings().digest_max_tickers
        ]
        fp = watchlist_ticker_fingerprint(wl.tickers)
        return "watchlist", tickers, f"watchlist:{watchlist_name}:{fp}"
    if key in ("sp100", "sp500"):
        return key, load_universe_tickers(key), key
    settings = get_settings()
    proactive = (settings.smart_money_proactive_universe or "sp500").strip().lower()
    if proactive == "watchlist":
        return resolve_scan_universe("watchlist", watchlist_name=watchlist_name)
    return proactive, load_universe_tickers(proactive), proactive


def scan_cache_ttl_seconds(universe_key: str, *, default_minutes: int) -> int:
    settings = get_settings()
    if universe_key == "sp500":
        return settings.smart_money_sp500_cache_minutes * 60
    return default_minutes * 60


def _result_from_cache(cached: dict[str, Any], result_type: type[R]) -> R:
    if cached.get("result"):
        return result_type(**cached["result"])
    return result_type(**cached)


def filter_scan_rows(
    rows: list[T],
    *,
    signals_only: bool,
    filter_row: Callable[[T], bool] | None,
) -> list[T]:
    if not signals_only:
        return rows
    if filter_row is None:
        return rows
    return [r for r in rows if filter_row(r)]


def apply_scan_response_filter(
    cached: dict[str, Any],
    result_type: type[R],
    build_result: Callable[..., R],
    *,
    filter_row: Callable[[T], bool] | None,
    signals_only: bool,
) -> R:
    """Load unified cache (all rows) and apply signals_only filter for the API response."""
    all_result = _result_from_cache(cached, result_type)
    all_rows = list(all_result.rows)  # type: ignore[attr-defined]
    filtered = filter_scan_rows(all_rows, signals_only=signals_only, filter_row=filter_row)
    return build_result(
        filtered,
        all_result.universe,  # type: ignore[attr-defined]
        all_result.scanned_count,  # type: ignore[attr-defined]
        all_result.as_of,  # type: ignore[attr-defined]
        fetched_count=all_result.fetched_count,  # type: ignore[attr-defined]
        signals_only=signals_only,
        partial=bool(cached.get("partial", False)),
        provider_degraded=getattr(all_result, "provider_degraded", False),
    )


def _effective_cache_ttl(
    *,
    cache_ttl_seconds: int,
    scanned_count: int,
    fetched_count: int,
    partial: bool,
) -> int:
    settings = get_settings()
    if not partial and scanned_count > 0 and fetched_count == 0:
        return settings.scan_failure_cache_seconds
    return cache_ttl_seconds


async def scan_universe_chunked(
    tickers: list[str],
    *,
    universe_key: str,
    cache_prefix: str,
    cache_key: str,
    cache_ttl_seconds: int,
    result_type: type[R],
    scan_one: Callable[[str], Awaitable[T | None]],
    build_result: Callable[..., R],
    filter_row: Callable[[T], bool] | None = None,
    signals_only: bool = True,
    refresh: bool = False,
    job_resource: str | None = None,
    job_name: str | None = None,
    prefetch_chunk: Callable[[list[str]], dict[str, Any]] | None = None,
    on_chunk_prefetched: Callable[[dict[str, Any]], None] | None = None,
) -> R:
    """Scan tickers in chunks with partial cache + WebSocket progress.

    Cache stores all fetched rows (unfiltered). ``signals_only`` is applied when
    building the returned API response.
    """
    if refresh:
        clear_cached(cache_prefix, cache_key)

    cached = get_cached(cache_prefix, cache_key)
    if cached and isinstance(cached, dict) and not refresh:
        return apply_scan_response_filter(
            cached,
            result_type,
            build_result,
            filter_row=filter_row,
            signals_only=signals_only,
        )

    if not tickers:
        return build_result(
            [],
            universe_key,
            0,
            datetime.now(UTC),
            fetched_count=0,
            signals_only=signals_only,
        )

    settings = get_settings()
    chunk_size = settings.yfinance_batch_chunk_size
    chunks = _chunk_symbols(tickers, chunk_size)
    resource = job_resource or cache_prefix
    as_of = datetime.now(UTC)
    all_fetched: list[T] = []
    sem = asyncio.Semaphore(settings.smart_money_scan_concurrency)
    processed = 0

    async def _one(sym: str) -> T | None:
        async with sem:
            return await scan_one(sym)

    for chunk_idx, chunk in enumerate(chunks):
        if prefetch_chunk is not None:
            hist_map = await asyncio.to_thread(prefetch_chunk, chunk)
            if on_chunk_prefetched is not None:
                on_chunk_prefetched(hist_map)
        scanned = await asyncio.gather(*[_one(sym) for sym in chunk])
        for row in scanned:
            if row is not None:
                all_fetched.append(row)
        processed += len(chunk)
        partial = processed < len(tickers)
        full_result = build_result(
            all_fetched,
            universe_key,
            processed,
            as_of,
            fetched_count=len(all_fetched),
            signals_only=False,
            partial=partial,
            provider_degraded=processed > 0 and len(all_fetched) == 0 and not partial,
        )
        chunk_ttl = _effective_cache_ttl(
            cache_ttl_seconds=cache_ttl_seconds,
            scanned_count=processed,
            fetched_count=len(all_fetched),
            partial=partial,
        )
        set_cached_ttl(
            cache_prefix,
            cache_key,
            {
                "as_of": as_of.isoformat(),
                "scanned_count": processed,
                "partial": partial,
                "result": full_result.model_dump(mode="json"),
            },
            chunk_ttl,
        )
        from trade_sentinel_api.services.job_events import publish_scan_progress

        publish_scan_progress(
            resource=resource,
            cache_key=cache_key,
            completed=processed,
            total=len(tickers),
            universe=universe_key,
            job_name=job_name,
        )
        if settings.yfinance_chunk_delay_seconds > 0 and partial:
            await asyncio.sleep(settings.yfinance_chunk_delay_seconds)

    filtered = filter_scan_rows(all_fetched, signals_only=signals_only, filter_row=filter_row)
    final_partial = False
    provider_degraded = len(tickers) > 0 and len(all_fetched) == 0
    final_ttl = _effective_cache_ttl(
        cache_ttl_seconds=cache_ttl_seconds,
        scanned_count=len(tickers),
        fetched_count=len(all_fetched),
        partial=final_partial,
    )
    final_result = build_result(
        all_fetched,
        universe_key,
        len(tickers),
        as_of,
        fetched_count=len(all_fetched),
        signals_only=False,
        partial=final_partial,
        provider_degraded=provider_degraded,
    )
    set_cached_ttl(
        cache_prefix,
        cache_key,
        {
            "as_of": as_of.isoformat(),
            "scanned_count": len(tickers),
            "partial": final_partial,
            "result": final_result.model_dump(mode="json"),
        },
        final_ttl,
    )
    return build_result(
        filtered,
        universe_key,
        len(tickers),
        as_of,
        fetched_count=len(all_fetched),
        signals_only=signals_only,
        partial=final_partial,
        provider_degraded=provider_degraded,
    )
