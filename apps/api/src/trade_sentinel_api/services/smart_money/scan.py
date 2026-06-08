"""Watchlist insider pulse, bounded universe scans, and feed-derived insider accumulation."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    InsiderScanResult,
    InsiderScanRow,
    InsiderTransaction,
    OptionsScanResult,
    OptionsScanRow,
    WatchlistInsiderPulse,
    WatchlistInsiderPulseRow,
)
from trade_sentinel_api.services.cache import clear_cached, get_cached, set_cached_ttl
from trade_sentinel_api.services.sec.edgar import fetch_insider_timeline, summarize_insider_activity
from trade_sentinel_api.services.options_tick_flow import enrich_options_flow_with_ticks
from trade_sentinel_api.services.scan_batch import (
    apply_scan_response_filter,
    resolve_scan_universe,
    scan_cache_ttl_seconds,
    scan_universe_chunked,
)
from trade_sentinel_api.services.watchlists import get_watchlist, watchlist_ticker_fingerprint

logger = logging.getLogger(__name__)

_PULSE_CACHE_TTL = 14400
_INSIDER_SCAN_TTL = 14400


def _sentiment_rank(sentiment: str) -> int:
    return {"accumulation": 0, "neutral": 1, "distribution": 2}.get(sentiment, 3)


def _options_rank(row: OptionsScanRow) -> tuple:
    ratio = row.put_call_ratio
    extreme = 0
    if ratio is not None:
        if ratio > 1.5 or ratio < 0.5:
            extreme = 1
    total_vol = (row.call_volume or 0) + (row.put_volume or 0)
    vol_oi = row.max_vol_oi_ratio or 0
    return (
        0 if row.unusual else 1,
        -row.unusual_contract_count,
        -vol_oi,
        -extreme,
        -total_vol,
    )


def _top_strike_summary(flow) -> str | None:
    if not flow.top_strikes:
        return None
    top = flow.top_strikes[0]
    return f"{top.side.upper()} ${top.strike:.0f} vol {top.volume:,.0f}"


def _options_signal_filter(universe_key: str):
    if universe_key in ("sp100", "sp500"):
        return lambda row: row.unusual
    return lambda _row: True


def _recent_transactions(transactions: list[InsiderTransaction], limit: int = 10) -> list[InsiderTransaction]:
    sorted_tx = sorted(transactions, key=lambda t: t.filing_date, reverse=True)
    return sorted_tx[:limit]


async def _pulse_row(symbol: str) -> WatchlistInsiderPulseRow:
    try:
        timeline = await fetch_insider_timeline(symbol)
        if not timeline.data_available or not timeline.transactions:
            return WatchlistInsiderPulseRow(ticker=symbol, data_available=False)
        summary = summarize_insider_activity(timeline.transactions)
        latest_notable = None
        if summary.notable_transactions:
            n = summary.notable_transactions[0]
            latest_notable = (
                f"{n.filing_date} {n.insider_name} {n.transaction_type}"
                f"{f' ${n.notional:,.0f}' if n.notional else ''}"
            )
        return WatchlistInsiderPulseRow(
            ticker=symbol,
            sentiment=summary.sentiment,
            net_shares_90d=summary.net_shares_90d,
            buy_count=summary.buy_count,
            sell_count=summary.sell_count,
            open_market_buy_count=summary.open_market_buy_count,
            cluster_buying=summary.cluster_buying,
            latest_notable=latest_notable,
            recent_transactions=_recent_transactions(timeline.transactions),
            data_available=summary.data_available,
        )
    except Exception:
        return WatchlistInsiderPulseRow(ticker=symbol, data_available=False)


async def build_watchlist_insider_pulse(
    watchlist_name: str = "default",
) -> WatchlistInsiderPulse:
    wl = get_watchlist(watchlist_name)
    tickers = [t.upper().strip() for t in wl.tickers if t.strip()][
        : get_settings().digest_max_tickers
    ]
    fp = watchlist_ticker_fingerprint(wl.tickers)
    cache_key = f"pulse:{watchlist_name}:{fp}"
    cached = get_cached("smart_money_pulse", cache_key)
    if cached:
        return WatchlistInsiderPulse(**cached)
    if not tickers:
        return WatchlistInsiderPulse(
            as_of=datetime.now(UTC),
            watchlist_name=watchlist_name,
            message="Watchlist is empty — add tickers to see insider pulse.",
        )

    sem = asyncio.Semaphore(get_settings().smart_money_scan_concurrency)

    async def one(sym: str) -> WatchlistInsiderPulseRow:
        async with sem:
            return await _pulse_row(sym)

    rows = list(await asyncio.gather(*[one(t) for t in tickers]))
    rows.sort(
        key=lambda r: (
            _sentiment_rank(r.sentiment),
            -r.buy_count,
            r.sell_count,
        )
    )
    available = any(r.data_available for r in rows)
    pulse = WatchlistInsiderPulse(
        as_of=datetime.now(UTC),
        watchlist_name=watchlist_name,
        rows=rows,
        data_available=available,
        message=None if available else "No insider Form 4 data for watchlist tickers.",
    )
    set_cached_ttl(
        "smart_money_pulse",
        cache_key,
        pulse.model_dump(mode="json"),
        _PULSE_CACHE_TTL,
    )
    return pulse


def _options_flow_has_data(flow) -> bool:
    if (flow.call_volume or 0) > 0 or (flow.put_volume or 0) > 0:
        return True
    if flow.put_call_ratio is not None:
        return True
    if getattr(flow, "open_interest_available", False):
        return True
    if getattr(flow, "expiry_breakdown", None):
        return True
    return False


async def _scan_one_option(symbol: str, *, max_attempts: int = 3) -> OptionsScanRow | None:
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            flow, _ = await enrich_options_flow_with_ticks(symbol)
            if not _options_flow_has_data(flow):
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return None
            sweep_count = len(flow.sweep_candidates or [])
            return OptionsScanRow(
                ticker=symbol,
                put_call_ratio=flow.put_call_ratio,
                unusual=flow.unusual or sweep_count > 0,
                unusual_reason=flow.unusual_reason
                or (f"{sweep_count} sweep candidate(s)" if sweep_count else None),
                call_volume=flow.call_volume,
                put_volume=flow.put_volume,
                top_strike_summary=_top_strike_summary(flow),
                unusual_contract_count=len(flow.unusual_contracts),
                max_vol_oi_ratio=flow.max_vol_oi_ratio,
                sweep_count=sweep_count,
                data_source=flow.data_source or "yfinance_aggregate",
            )
        except Exception as exc:
            last_exc = exc
            logger.debug("options_scan_failed ticker=%s attempt=%s error=%s", symbol, attempt + 1, exc)
            if attempt < max_attempts - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
    if last_exc is not None:
        logger.debug("options_scan_exhausted ticker=%s error=%s", symbol, last_exc)
    return None


def _build_options_result(
    rows: list[OptionsScanRow],
    universe_key: str,
    scanned_count: int,
    as_of: datetime,
    *,
    fetched_count: int = 0,
    signals_only: bool = True,
    partial: bool = False,
    provider_degraded: bool = False,
) -> OptionsScanResult:
    sorted_rows = sorted(rows, key=_options_rank)
    message = None
    if not sorted_rows:
        if fetched_count == 0:
            message = "Options data could not be fetched for this universe."
        elif signals_only:
            message = (
                f"No unusual options activity in {universe_key} today "
                f"({fetched_count} tickers scanned)."
            )
        else:
            message = "No options chain data available for this universe."
    return OptionsScanResult(
        as_of=as_of,
        universe=universe_key,  # type: ignore[arg-type]
        rows=sorted_rows,
        scanned_count=scanned_count,
        fetched_count=fetched_count,
        data_available=len(sorted_rows) > 0,
        message=message,
        partial=partial,
        provider_degraded=provider_degraded,
    )


async def scan_options_universe(
    universe: str = "sp500",
    watchlist_name: str = "default",
    *,
    signals_only: bool = True,
    refresh: bool = False,
) -> OptionsScanResult:
    universe_key, tickers, cache_suffix = resolve_scan_universe(universe, watchlist_name=watchlist_name)
    cache_key = f"options:{cache_suffix}"
    cached = get_cached("smart_money_options", cache_key)
    if cached and isinstance(cached, dict) and not refresh:
        return apply_scan_response_filter(
            cached,
            OptionsScanResult,
            _build_options_result,
            filter_row=_options_signal_filter(universe_key),
            signals_only=signals_only,
        )

    if universe_key == "watchlist" and len(tickers) <= get_settings().digest_max_tickers:
        sem = asyncio.Semaphore(get_settings().smart_money_scan_concurrency)

        async def one(sym: str) -> OptionsScanRow | None:
            async with sem:
                return await _scan_one_option(sym)

        scanned = list(await asyncio.gather(*[one(t) for t in tickers]))
        fetched = [r for r in scanned if r is not None]
        provider_degraded = len(tickers) > 0 and len(fetched) == 0
        full_result = _build_options_result(
            fetched,
            universe_key,
            len(tickers),
            datetime.now(UTC),
            fetched_count=len(fetched),
            signals_only=False,
            provider_degraded=provider_degraded,
        )
        settings = get_settings()
        ttl = (
            settings.scan_failure_cache_seconds
            if provider_degraded
            else settings.smart_money_options_cache_minutes * 60
        )
        set_cached_ttl(
            "smart_money_options",
            cache_key,
            {
                "as_of": full_result.as_of.isoformat(),
                "scanned_count": len(tickers),
                "partial": False,
                "result": full_result.model_dump(mode="json"),
            },
            ttl,
        )
        if signals_only:
            filtered = [r for r in fetched if _options_signal_filter(universe_key)(r)]
            return _build_options_result(
                filtered,
                universe_key,
                len(tickers),
                full_result.as_of,
                fetched_count=len(fetched),
                signals_only=True,
                provider_degraded=provider_degraded,
            )
        return full_result

    ttl = scan_cache_ttl_seconds(universe_key, default_minutes=get_settings().smart_money_options_cache_minutes)
    options_job = {
        "watchlist": "options_watchlist",
        "sp100": "options_sp100",
        "sp500": "options_sp500",
    }.get(universe_key, "options_sp500")
    return await scan_universe_chunked(
        tickers,
        universe_key=universe_key,
        cache_prefix="smart_money_options",
        cache_key=cache_key,
        cache_ttl_seconds=ttl,
        result_type=OptionsScanResult,
        scan_one=_scan_one_option,
        build_result=_build_options_result,
        filter_row=_options_signal_filter(universe_key),
        signals_only=signals_only,
        refresh=refresh,
        job_resource="options_scan",
        job_name=options_job,
    )


async def _scan_one_insider(symbol: str) -> InsiderScanRow | None:
    try:
        timeline = await fetch_insider_timeline(symbol)
        if not timeline.data_available or not timeline.transactions:
            return None
        summary = summarize_insider_activity(timeline.transactions)
        latest_notable = None
        if summary.notable_transactions:
            n = summary.notable_transactions[0]
            latest_notable = (
                f"{n.filing_date} {n.insider_name} {n.transaction_type}"
                f"{f' ${n.notional:,.0f}' if n.notional else ''}"
            )
        notable_buy_count = sum(
            1
            for n in summary.notable_transactions
            if "purchase" in (n.transaction_type or "").lower()
            or "buy" in (n.transaction_type or "").lower()
        )
        return InsiderScanRow(
            ticker=symbol,
            sentiment=summary.sentiment,
            buy_count=summary.buy_count,
            sell_count=summary.sell_count,
            cluster_buying=summary.cluster_buying,
            notable_buy_count=notable_buy_count,
            net_shares_90d=summary.net_shares_90d,
            open_market_buy_count=summary.open_market_buy_count,
            latest_notable=latest_notable,
            recent_transactions=_recent_transactions(timeline.transactions),
            data_available=summary.data_available,
        )
    except Exception:
        return None


def _insider_signal_filter(row: InsiderScanRow) -> bool:
    return row.sentiment == "accumulation" or row.cluster_buying


def _build_insider_result(
    rows: list[InsiderScanRow],
    universe_key: str,
    scanned_count: int,
    as_of: datetime,
    *,
    fetched_count: int = 0,
    signals_only: bool = True,
    partial: bool = False,
    provider_degraded: bool = False,
) -> InsiderScanResult:
    del signals_only
    sorted_rows = sorted(
        rows,
        key=lambda r: (
            0 if r.cluster_buying else 1,
            -r.buy_count,
            r.sell_count,
        ),
    )
    message = None
    if not sorted_rows:
        if provider_degraded:
            message = "Insider Form 4 data could not be fetched for this universe."
        else:
            message = f"No accumulation signals in {universe_key.upper()} from insider Form 4 data."
    return InsiderScanResult(
        as_of=as_of,
        universe=universe_key,  # type: ignore[arg-type]
        rows=sorted_rows,
        scanned_count=scanned_count,
        fetched_count=fetched_count,
        data_available=len(sorted_rows) > 0,
        message=message,
        partial=partial,
        provider_degraded=provider_degraded,
    )


async def scan_insider_universe(
    universe: str = "sp500",
    *,
    refresh: bool = False,
) -> InsiderScanResult:
    universe_key, tickers, cache_suffix = resolve_scan_universe(universe)
    cache_key = f"v3:insider:{cache_suffix}"
    if refresh:
        clear_cached("smart_money_insider", cache_key)

    cached = get_cached("smart_money_insider", cache_key)
    if cached and not refresh:
        if isinstance(cached, dict) and cached.get("result"):
            return InsiderScanResult(**cached["result"])
        return InsiderScanResult(**cached)

    if not tickers:
        return InsiderScanResult(
            as_of=datetime.now(UTC),
            universe=universe_key,  # type: ignore[arg-type]
            message="No tickers in selected universe.",
        )

    if universe_key == "watchlist":
        sem = asyncio.Semaphore(get_settings().smart_money_scan_concurrency)

        async def one(sym: str) -> InsiderScanRow | None:
            async with sem:
                return await _scan_one_insider(sym)

        scanned = list(await asyncio.gather(*[one(t) for t in tickers]))
        data_fetched = [r for r in scanned if r is not None]
        candidates = [r for r in data_fetched if _insider_signal_filter(r)]
        provider_degraded = len(tickers) > 0 and len(data_fetched) == 0
        result = _build_insider_result(
            candidates,
            universe_key,
            len(tickers),
            datetime.now(UTC),
            fetched_count=len(data_fetched),
            provider_degraded=provider_degraded,
        )
        set_cached_ttl(
            "smart_money_insider",
            cache_key,
            {"result": result.model_dump(mode="json")},
            _INSIDER_SCAN_TTL,
        )
        return result

    return await scan_universe_chunked(
        tickers,
        universe_key=universe_key,
        cache_prefix="smart_money_insider",
        cache_key=cache_key,
        cache_ttl_seconds=_INSIDER_SCAN_TTL,
        result_type=InsiderScanResult,
        scan_one=_scan_one_insider,
        build_result=_build_insider_result,
        filter_row=_insider_signal_filter,
        signals_only=True,
        refresh=refresh,
        job_resource="insider_scan",
        job_name="insider_sp500",
    )
