"""Market and watchlist screener filters and queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import DigestTickerRow, ScreenerResult, ScreenerRow
from trade_sentinel_api.services.digest.cache_keys import (
    _normalize_universe,
    market_screener_cache_key,
)
from trade_sentinel_api.services.universe import load_universe_tickers


def _digest():
    from trade_sentinel_api.services import digest as digest_svc

    return digest_svc


@dataclass
class ScreenerFilterParams:
    mos_min: float | None = None
    mos_max: float | None = None
    mos_label: str | None = None
    pe_max: float | None = None
    valuation_label: str | None = None
    has_earnings_within_days: int | None = None
    insider_sentiment: str | None = None
    warning_any: str | None = None


def resolve_screener_filters(
    *,
    preset: str | None = None,
    mos_min: float | None = None,
    mos_max: float | None = None,
    pe_max: float | None = None,
    valuation_label: str | None = None,
    has_earnings_within_days: int | None = None,
    insider_sentiment: str | None = None,
    warning_any: str | None = None,
) -> ScreenerFilterParams:
    mos_label: str | None = None
    if preset == "undervalued":
        mos_label = "undervalued"
    elif preset == "earnings_week":
        has_earnings_within_days = has_earnings_within_days or 7
    elif preset == "insider_accumulation":
        insider_sentiment = insider_sentiment or "accumulation"
    elif preset == "insider_cluster_buy":
        insider_sentiment = insider_sentiment or "accumulation"
    elif preset == "options_unusual":
        warning_any = warning_any or "OPTIONS_UNUSUAL"
    elif preset == "high_risk":
        warning_any = warning_any or "PRICE_ABOVE_FAIR_VALUE"
    elif preset == "institutional_conviction":
        pass

    return ScreenerFilterParams(
        mos_min=mos_min,
        mos_max=mos_max,
        mos_label=mos_label,
        pe_max=pe_max,
        valuation_label=valuation_label,
        has_earnings_within_days=has_earnings_within_days,
        insider_sentiment=insider_sentiment,
        warning_any=warning_any,
    )


def _rank_score(row: DigestTickerRow, preset: str | None) -> float:
    if row.mos_pct is None:
        return 999.0 if preset == "undervalued" else -999.0
    return row.mos_pct


def apply_screener_filters(
    rows: list[DigestTickerRow],
    filters: ScreenerFilterParams,
    *,
    preset: str | None = None,
) -> list[ScreenerRow]:
    matched: list[ScreenerRow] = []

    for row in rows:
        if filters.mos_label and row.mos_label != filters.mos_label:
            continue
        if filters.mos_min is not None and (row.mos_pct is None or row.mos_pct < filters.mos_min):
            continue
        if filters.mos_max is not None and (row.mos_pct is None or row.mos_pct > filters.mos_max):
            continue
        if filters.pe_max is not None and (row.pe_forward is None or row.pe_forward > filters.pe_max):
            continue
        if filters.valuation_label and row.valuation_label != filters.valuation_label:
            continue
        if filters.has_earnings_within_days is not None:
            if row.earnings_days is None or row.earnings_days > filters.has_earnings_within_days:
                continue
        if filters.warning_any and row.top_warning != filters.warning_any:
            continue
        if filters.insider_sentiment and row.insider_sentiment != filters.insider_sentiment:
            continue
        matched.append(ScreenerRow(**row.model_dump(), rank_score=_rank_score(row, preset)))

    if preset == "undervalued":
        matched.sort(key=lambda r: r.rank_score if r.rank_score is not None else 999.0)
    else:
        matched.sort(key=lambda r: r.rank_score or -999, reverse=True)

    return matched


async def _build_market_lite_rows(
    universe: str,
    *,
    refresh: bool = False,
) -> tuple[list[DigestTickerRow], int, datetime | None, bool]:
    universe_key = _normalize_universe(universe)
    cache_key = market_screener_cache_key(universe_key)
    tickers = load_universe_tickers(universe_key)
    settings = _digest().get_settings()
    ttl = settings.market_screener_cache_minutes * 60

    cached = _digest().get_cached("market_screener", cache_key)
    if refresh and settings.background_jobs_enabled:
        from trade_sentinel_api.services.scheduler.scheduling import (
            schedule_market_screener_refresh,
        )

        schedule_market_screener_refresh()
        if cached and cached.get("rows"):
            rows = [DigestTickerRow(**r) for r in cached["rows"]]
            cached_at_raw = cached.get("cached_at")
            cached_at = (
                datetime.fromisoformat(cached_at_raw)
                if isinstance(cached_at_raw, str)
                else None
            )
            scanned = len(rows) if cached.get("partial") else len(tickers)
            return rows, scanned, cached_at, True
        return [], len(tickers), None, True

    if cached and cached.get("rows") and not refresh:
        rows = [DigestTickerRow(**r) for r in cached["rows"]]
        cached_at_raw = cached.get("cached_at")
        cached_at = (
            datetime.fromisoformat(cached_at_raw)
            if isinstance(cached_at_raw, str)
            else None
        )
        return rows, len(rows), cached_at, False

    if not refresh and settings.background_jobs_enabled:
        from trade_sentinel_api.services.scheduler.scheduling import (
            schedule_market_screener_refresh,
        )

        schedule_market_screener_refresh()
        if cached and cached.get("rows"):
            rows = [DigestTickerRow(**r) for r in cached["rows"]]
            cached_at_raw = cached.get("cached_at")
            cached_at = (
                datetime.fromisoformat(cached_at_raw)
                if isinstance(cached_at_raw, str)
                else None
            )
            return rows, len(rows), cached_at, True
        return [], len(tickers), None, True

    rows, cached_at = await _digest().build_lite_rows_batch(
        tickers,
        refresh=refresh,
        cache_prefix="market_screener",
        cache_key=cache_key,
        cache_ttl_seconds=ttl,
        max_workers=settings.background_scan_workers if refresh else None,
        include_insider=False,
    )
    return rows, len(tickers), cached_at, False


async def screen_market_universe(
    *,
    universe: str = "sp500",
    refresh: bool = False,
    mos_min: float | None = None,
    mos_max: float | None = None,
    pe_max: float | None = None,
    valuation_label: str | None = None,
    has_earnings_within_days: int | None = None,
    insider_sentiment: str | None = None,
    warning_any: str | None = None,
    preset: str | None = None,
) -> ScreenerResult:
    universe_key = _normalize_universe(universe)
    filters = resolve_screener_filters(
        preset=preset,
        mos_min=mos_min,
        mos_max=mos_max,
        pe_max=pe_max,
        valuation_label=valuation_label,
        has_earnings_within_days=has_earnings_within_days,
        insider_sentiment=insider_sentiment,
        warning_any=warning_any,
    )

    all_rows, scanned_count, cached_at, stale = await _digest()._build_market_lite_rows(
        universe_key, refresh=refresh
    )

    if preset == "institutional_conviction":
        from trade_sentinel_api.services.sec.form13f import scan_institutional_conviction

        conviction = await scan_institutional_conviction(universe_key)
        conviction_tickers = {r.ticker.upper() for r in conviction.rows if r.conviction_buy}
        rows = [
            ScreenerRow(**r.model_dump(), rank_score=_rank_score(r, preset))
            for r in all_rows
            if r.ticker.upper() in conviction_tickers
        ]
        return ScreenerResult(
            as_of=datetime.now(UTC),
            universe=universe_key,
            preset=preset,
            scanned_count=scanned_count,
            cached_at=cached_at,
            stale=stale,
            rows=rows,
            empty_message="No tickers in this universe match these filters."
            if all_rows and not rows
            else None,
        )

    if stale and not all_rows:
        return ScreenerResult(
            as_of=datetime.now(UTC),
            universe=universe_key,
            preset=preset,
            scanned_count=scanned_count,
            rows=[],
            stale=True,
            empty_message=(
                "Market screener cache is warming up in the background "
                f"({scanned_count} tickers in universe). Rows will appear as the scan progresses."
            ),
        )

    if stale and all_rows:
        rows = apply_screener_filters(all_rows, filters, preset=preset)
        return ScreenerResult(
            as_of=datetime.now(UTC),
            universe=universe_key,
            preset=preset,
            scanned_count=scanned_count,
            cached_at=cached_at,
            stale=True,
            rows=rows,
            empty_message="No tickers in this universe match these filters."
            if all_rows and not rows
            else None,
        )

    if not all_rows and not stale:
        return ScreenerResult(
            as_of=datetime.now(UTC),
            universe=universe_key,
            preset=preset,
            scanned_count=0,
            empty_message=f"Market universe is empty — check {universe_key}_universe.json.",
        )

    rows = apply_screener_filters(all_rows, filters, preset=preset)

    return ScreenerResult(
        as_of=datetime.now(UTC),
        universe=universe_key,
        preset=preset,
        scanned_count=scanned_count,
        cached_at=cached_at,
        stale=stale,
        rows=rows,
        empty_message="No tickers in this universe match these filters."
        if all_rows and not rows
        else None,
    )


async def screen_watchlist(
    *,
    watchlist_name: str = "default",
    refresh: bool = False,
    mos_min: float | None = None,
    mos_max: float | None = None,
    pe_max: float | None = None,
    valuation_label: str | None = None,
    has_earnings_within_days: int | None = None,
    insider_sentiment: str | None = None,
    warning_any: str | None = None,
    preset: str | None = None,
) -> ScreenerResult:
    filters = resolve_screener_filters(
        preset=preset,
        mos_min=mos_min,
        mos_max=mos_max,
        pe_max=pe_max,
        valuation_label=valuation_label,
        has_earnings_within_days=has_earnings_within_days,
        insider_sentiment=insider_sentiment,
        warning_any=warning_any,
    )

    digest = await _digest().build_digest_today(watchlist_name, refresh=refresh)

    if preset == "institutional_conviction":
        from trade_sentinel_api.services.sec.form13f import scan_institutional_conviction

        conviction = await scan_institutional_conviction("watchlist")
        conviction_tickers = {r.ticker.upper() for r in conviction.rows if r.conviction_buy}
        rows = [
            ScreenerRow(**r.model_dump(), rank_score=_rank_score(r, preset))
            for r in digest.tickers
            if r.ticker.upper() in conviction_tickers
        ]
    else:
        rows = apply_screener_filters(digest.tickers, filters, preset=preset)
    settings = get_settings()
    stale = (
        refresh
        and settings.background_jobs_enabled
        and bool(digest.tickers or digest.empty_message)
    )

    return ScreenerResult(
        as_of=datetime.now(UTC),
        universe="watchlist",
        preset=preset,
        scanned_count=len(digest.tickers),
        stale=stale,
        rows=rows,
        empty_message="No watchlist tickers match these filters."
        if digest.tickers and not rows
        else digest.empty_message,
    )
