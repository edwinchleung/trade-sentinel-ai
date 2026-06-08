"""Lite digest row builders and batch scans."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from trade_sentinel_api.models.schemas import DigestTickerRow
from trade_sentinel_api.services.digest.cache_keys import _trading_date_key
from trade_sentinel_api.services.macro.context import macro_overlay_for_ticker
from trade_sentinel_api.services.sec.edgar import _fetch_form4_sync, summarize_insider_activity
from trade_sentinel_api.services.sector_context import (
    enrich_digest_row_sector_fields,
    get_sector_universe_stats,
)
from trade_sentinel_api.services.ticker_valuation import (
    hydrate_digest_row,
    valuation_digest_fields,
)
from trade_sentinel_api.services.warnings import build_fundamental_warnings

logger = logging.getLogger(__name__)


def _digest():
    from trade_sentinel_api.services import digest as digest_svc

    return digest_svc


async def _hydrate_digest_rows(rows: list[DigestTickerRow]) -> list[DigestTickerRow]:
    if not rows:
        return rows
    return list(await asyncio.gather(*[hydrate_digest_row(r) for r in rows]))


def build_lite_row_sync(
    symbol: str,
    macro_bundle,
    *,
    include_insider: bool = False,
    bundle=None,
) -> DigestTickerRow:
    """Blocking lite row for thread-pool batch scans."""
    sym = symbol.upper().strip()
    try:
        bundle = bundle or _digest().load_ticker_bundle_sync(sym)
        market = _digest().market_from_bundle(bundle)
        price = market.get("price")
        fundamentals = _digest().fundamentals_from_bundle(bundle, price)
        if price is None or price <= 0:
            fundamentals, valuation = _digest().resolve_ticker_valuation_sync(sym, 0.0, fundamentals)
        else:
            fundamentals, valuation = _digest().resolve_ticker_valuation_sync(sym, price, fundamentals)
        earnings = _digest().earnings_from_bundle(bundle)
        fund_warnings = build_fundamental_warnings(fundamentals, earnings, valuation)
        top_warning = fund_warnings[0].code if fund_warnings else None

        insider_sentiment = None
        if include_insider:
            try:
                insider = _fetch_form4_sync(sym, limit=10)
                if insider.data_available and insider.transactions:
                    summary = summarize_insider_activity(insider.transactions)
                    if summary.data_available:
                        insider_sentiment = summary.sentiment
            except Exception:
                pass

        sector = fundamentals.sector if fundamentals else None
        overlay = macro_overlay_for_ticker(sym, sector, macro_bundle)
        macro_headline = None
        if overlay.has_content:
            macro_headline = overlay.market_weather or (
                overlay.headline_events[0] if overlay.headline_events else None
            )

        row = DigestTickerRow(
            ticker=sym,
            price=price,
            change_pct=market.get("change_pct"),
            top_warning=top_warning,
            earnings_days=earnings.days_until if earnings else None,
            insider_sentiment=insider_sentiment,
            macro_headline=macro_headline,
            pe_forward=fundamentals.pe_forward if fundamentals else None,
            sector=fundamentals.sector if fundamentals else None,
            **valuation_digest_fields(valuation, fundamentals),
        )
        try:
            stats = get_sector_universe_stats("sp500")
            row = enrich_digest_row_sector_fields(row, universe="sp500", stats=stats)
        except Exception:
            pass
        if row.price is None:
            from trade_sentinel_api.services.yfinance_logging import record_yfinance_batch_failure

            record_yfinance_batch_failure()
        return row
    except Exception as exc:
        from trade_sentinel_api.services.yfinance_logging import record_yfinance_batch_failure

        record_yfinance_batch_failure()
        logger.warning("Sync lite row failed for %s: %s", sym, exc)
        return DigestTickerRow(ticker=sym)


async def build_lite_rows_batch(
    tickers: list[str],
    *,
    refresh: bool = False,
    cache_prefix: str,
    cache_key: str,
    cache_ttl_seconds: int,
    max_workers: int | None = None,
    include_insider: bool = False,
) -> tuple[list[DigestTickerRow], datetime | None]:
    if refresh:
        _digest().clear_cached(cache_prefix, cache_key)

    cached = _digest().get_cached(cache_prefix, cache_key)
    cached_rows = None
    if cached:
        cached_rows = cached.get("rows") or (
            cached.get("tickers") if cache_prefix == "digest" else None
        )
    if cached_rows and not refresh:
        rows = [DigestTickerRow(**r) for r in cached_rows]
        cached_at_raw = cached.get("cached_at")
        cached_at = (
            datetime.fromisoformat(cached_at_raw)
            if isinstance(cached_at_raw, str)
            else None
        )
        return rows, cached_at

    if not tickers:
        return [], None

    macro_bundle = await _digest().get_daily_macro_bundle()
    settings = _digest().get_settings()

    total = len(tickers)
    cached_at_start = datetime.now(UTC)

    if max_workers is not None and max_workers > 0:
        from trade_sentinel_api.services.job_events import after_chunk_cached
        from trade_sentinel_api.services.yfinance_bundle import (
            _chunk_symbols,
            load_ticker_bundle_sync,
            prefetch_hist_chunk,
        )
        from trade_sentinel_api.services.yfinance_logging import yfinance_batch_context

        executor = _digest().get_scan_executor()
        loop = asyncio.get_running_loop()
        chunk_size = settings.yfinance_batch_chunk_size
        chunks = _chunk_symbols(tickers, chunk_size)
        rows: list[DigestTickerRow] = []

        with yfinance_batch_context(label=cache_prefix, total=total):
            for chunk_idx, chunk in enumerate(chunks):
                hist_map = await asyncio.to_thread(prefetch_hist_chunk, chunk)

                def _one(sym: str) -> DigestTickerRow:
                    bundle = load_ticker_bundle_sync(
                        sym,
                        hist_prefetch=hist_map.get(sym.upper()),
                    )
                    return _digest().build_lite_row_sync(
                        sym,
                        macro_bundle,
                        include_insider=include_insider,
                        bundle=bundle,
                    )

                chunk_rows = list(
                    await asyncio.gather(
                        *[loop.run_in_executor(executor, _one, sym) for sym in chunk]
                    )
                )
                rows.extend(chunk_rows)
                completed = len(rows)
                after_chunk_cached(
                    cache_prefix=cache_prefix,
                    cache_key=cache_key,
                    all_rows=rows,
                    chunk_rows=chunk_rows,
                    completed=completed,
                    total=total,
                    cache_ttl_seconds=cache_ttl_seconds,
                    cached_at=cached_at_start,
                )
                if chunk_idx < len(chunks) - 1 and settings.yfinance_chunk_delay_seconds > 0:
                    await asyncio.sleep(settings.yfinance_chunk_delay_seconds)
    else:
        workers = settings.digest_concurrency
        sem = asyncio.Semaphore(workers)

        async def one(sym: str) -> DigestTickerRow:
            async with sem:
                return await _lite_row(sym, macro_bundle, include_insider=include_insider)

        rows = list(await asyncio.gather(*[one(t) for t in tickers]))

    cached_at = datetime.now(UTC)
    row_dicts = [r.model_dump(mode="json") for r in rows]
    if cache_prefix == "digest":
        parts = cache_key.split(":")
        trading_date = parts[0] if parts else _trading_date_key()
        wl = parts[1] if len(parts) >= 2 else "default"
        _digest().set_cached_ttl(
            "digest",
            cache_key,
            {
                "as_of": cached_at.isoformat(),
                "trading_date": trading_date,
                "watchlist_name": wl,
                "tickers": row_dicts,
                "partial": False,
            },
            cache_ttl_seconds,
        )
    else:
        _digest().set_cached_ttl(
            cache_prefix,
            cache_key,
            {
                "rows": row_dicts,
                "cached_at": cached_at.isoformat(),
                "partial": False,
            },
            cache_ttl_seconds,
        )
    return rows, cached_at


async def _lite_row(
    symbol: str,
    macro_bundle,
    *,
    include_insider: bool = True,
) -> DigestTickerRow:
    try:
        return await _lite_row_inner(symbol, macro_bundle, include_insider=include_insider)
    except Exception as exc:
        logger.warning("Digest lite row failed for %s: %s", symbol, exc)
        return DigestTickerRow(ticker=symbol)


async def _lite_row_inner(
    symbol: str,
    macro_bundle,
    *,
    include_insider: bool = True,
) -> DigestTickerRow:
    sym = symbol.upper().strip()
    return await asyncio.to_thread(
        _digest().build_lite_row_sync,
        sym,
        macro_bundle,
        include_insider=include_insider,
    )
