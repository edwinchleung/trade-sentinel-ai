"""Market-wide Form 4 insider feed via EdgarTools date-range filings."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    SmartMoneyFeed,
    SmartMoneyFeedItem,
    SmartMoneyFeedStats,
)
from trade_sentinel_api.services.cache import clear_cached, get_cached, set_cached_ttl
from trade_sentinel_api.services.sec.adapter import (
    fetch_form3_by_date_range,
    fetch_form4_by_date_range,
    fetch_form5_by_date_range,
    filing_to_feed_items,
    filing_to_form3_feed_item,
)
from trade_sentinel_api.services.sec.insider_classification import detect_cluster_buying_by_ticker
from trade_sentinel_api.services.sec.http import SecRateLimitError

_STALE_FEED_SNAPSHOTS: dict[str, dict] = {}
_MAX_ENRICH = 200
_MAX_ENRICH_CAP = 200


def resolve_feed_date_range(
    *,
    days: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[date, date, int]:
    """Return (start, end, days_window) capped to configured max range."""
    settings = get_settings()
    max_range = settings.smart_money_feed_max_range_days
    today = date.today()

    if start_date is not None or end_date is not None:
        end = end_date or today
        start = start_date or end
        if start > end:
            start, end = end, start
        if end > today:
            end = today
        if start > end:
            start = end
    else:
        window = days if days is not None else settings.smart_money_feed_default_days
        window = max(1, min(max_range, window))
        end = today
        start = end - timedelta(days=window - 1)

    span = (end - start).days + 1
    if span > max_range:
        start = end - timedelta(days=max_range - 1)
        span = max_range

    return start, end, span


def _raw_cache_key(start: date, end: date) -> str:
    return f"v3_raw:{start.isoformat()}:{end.isoformat()}"


def _is_transient_raw_failure(raw: dict) -> bool:
    if raw.get("data_available", True):
        return False
    msg = (raw.get("message") or "").lower()
    return "unavailable" in msg or "rate limit" in msg or "429" in msg


def _cache_raw_feed_result(cache_key: str, raw: dict) -> None:
    settings = get_settings()
    if _is_transient_raw_failure(raw):
        set_cached_ttl(
            "smart_money_feed_raw",
            cache_key,
            raw,
            settings.sec_failure_cache_seconds,
        )
        return
    _STALE_FEED_SNAPSHOTS[cache_key] = raw
    set_cached_ttl(
        "smart_money_feed_raw",
        cache_key,
        raw,
        settings.smart_money_feed_cache_minutes * 60,
    )


def _build_stats(items: list[SmartMoneyFeedItem]) -> SmartMoneyFeedStats:
    buy_count = sum(1 for i in items if i.side == "buy")
    sell_count = sum(1 for i in items if i.side == "sell")
    other_count = sum(1 for i in items if i.side == "other")
    notionals = [i.notional for i in items if i.notional is not None]
    total_notional = round(sum(notionals), 2) if notionals else None
    ticker_counts: dict[str, int] = {}
    for item in items:
        if item.ticker:
            ticker_counts[item.ticker] = ticker_counts.get(item.ticker, 0) + 1
    top_tickers = sorted(ticker_counts, key=ticker_counts.get, reverse=True)[:5]
    return SmartMoneyFeedStats(
        buy_count=buy_count,
        sell_count=sell_count,
        other_count=other_count,
        total_notional=total_notional,
        top_tickers=top_tickers,
    )


def _apply_filters(
    items: list[SmartMoneyFeedItem],
    *,
    start_date: date,
    end_date: date,
    side: str,
    notable_only: bool,
    min_notional: float | None,
    open_market_only: bool,
    cluster_only: bool,
) -> list[SmartMoneyFeedItem]:
    filtered: list[SmartMoneyFeedItem] = []
    for item in items:
        try:
            filing = date.fromisoformat(item.filing_date[:10])
        except ValueError:
            filing = date.today()
        if filing < start_date or filing > end_date:
            continue
        if open_market_only and not item.is_open_market:
            continue
        if cluster_only and not item.cluster_buying:
            continue
        if side == "buy" and item.side != "buy":
            continue
        if side == "sell" and item.side != "sell":
            continue
        if notable_only and not item.is_notable:
            continue
        if min_notional is not None:
            if item.notional is None or item.notional < min_notional:
                continue
        filtered.append(item)
    return filtered


def _range_label(start_date: date, end_date: date) -> str:
    if start_date == end_date:
        return f"on {start_date.isoformat()}"
    return f"from {start_date.isoformat()} to {end_date.isoformat()}"


def _empty_filter_message(
    *,
    start_date: date,
    end_date: date,
    side: str,
    notable_only: bool,
    cluster_only: bool,
    open_market_only: bool,
    enriched_count: int,
    raw_entry_count: int,
    items: list[SmartMoneyFeedItem],
) -> str:
    range_note = _range_label(start_date, end_date)
    open_market_items = [i for i in items if i.is_open_market]
    buy_count = sum(1 for i in open_market_items if i.side == "buy")
    sell_count = sum(1 for i in open_market_items if i.side == "sell")
    parsed_note = f"({enriched_count} filings parsed"
    if buy_count or sell_count:
        parsed_note += f"; {buy_count} buys, {sell_count} sells in sample"
    parsed_note += ")"

    if cluster_only:
        return f"No cluster buys (2+ insiders buying the same ticker) {range_note}. {parsed_note}."
    if notable_only:
        return f"No open-market trades over $1M notional {range_note}. {parsed_note}."
    if side == "sell":
        return f"No open-market sells {range_note}. {parsed_note}."
    if side == "buy":
        return f"No open-market buys {range_note}. {parsed_note}."
    if open_market_only:
        return (
            f"No open-market Form 4 trades {range_note}. "
            f"{parsed_note}; try disabling open-market filter.)"
        )
    return f"No Form 4 trades match these filters ({raw_entry_count} SEC entries scanned)."


def _items_from_raw_pool(raw: dict) -> list[SmartMoneyFeedItem]:
    return [SmartMoneyFeedItem(**item) for item in raw.get("items", [])]


def _parse_raw_dates(raw: dict) -> tuple[date, date, int]:
    start_s = raw.get("start_date")
    end_s = raw.get("end_date")
    if start_s and end_s:
        try:
            start = date.fromisoformat(str(start_s)[:10])
            end = date.fromisoformat(str(end_s)[:10])
            days = raw.get("days_window") or (end - start).days + 1
            return start, end, int(days)
        except ValueError:
            pass
    days = int(raw.get("days_window", 1))
    end = date.today()
    start = end - timedelta(days=max(days, 1) - 1)
    return start, end, days


def _build_feed_from_raw(
    raw: dict,
    *,
    side: str,
    notable_only: bool,
    min_notional: float | None,
    open_market_only: bool,
    cluster_only: bool,
    sec_rate_limited: bool = False,
) -> SmartMoneyFeed:
    start_date, end_date, days = _parse_raw_dates(raw)
    as_of = raw.get("as_of")
    if isinstance(as_of, str):
        as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    else:
        as_of_dt = datetime.now(UTC)

    if not raw.get("data_available", True):
        return SmartMoneyFeed(
            as_of=as_of_dt,
            data_available=False,
            message=raw.get("message"),
            days_window=days,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            sec_rate_limited=sec_rate_limited,
        )

    items = _items_from_raw_pool(raw)
    filtered = _apply_filters(
        items,
        start_date=start_date,
        end_date=end_date,
        side=side,
        notable_only=notable_only,
        min_notional=min_notional,
        open_market_only=open_market_only,
        cluster_only=cluster_only,
    )

    enriched_count = raw.get("enriched_count", 0)
    raw_entry_count = raw.get("raw_entry_count", 0)
    if not filtered and items:
        msg = _empty_filter_message(
            start_date=start_date,
            end_date=end_date,
            side=side,
            notable_only=notable_only,
            cluster_only=cluster_only,
            open_market_only=open_market_only,
            enriched_count=enriched_count,
            raw_entry_count=raw_entry_count,
            items=items,
        )
    elif not filtered:
        msg = f"No Form 4 trades match these filters ({raw_entry_count} SEC entries scanned)."
    else:
        msg = None

    if sec_rate_limited:
        msg = "SEC rate limited — showing last cached Form 4 feed."

    sec_data_available = bool(raw.get("data_available", True)) and (
        len(items) > 0 or raw_entry_count > 0
    )

    return SmartMoneyFeed(
        as_of=as_of_dt,
        items=filtered,
        stats=_build_stats(filtered),
        data_available=sec_data_available,
        message=msg,
        days_window=days,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        raw_entry_count=raw_entry_count,
        enriched_count=enriched_count,
        parse_failed_count=raw.get("parse_failed_count", 0),
        xml_attempt_count=raw.get("xml_attempt_count", 0),
        filtered_count=len(filtered),
        sec_rate_limited=sec_rate_limited,
    )


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "too many" in msg


def _fetch_forms_sync(*, start: date, end: date, enrich_limit: int, form_type: str) -> tuple[list, int]:
    settings = get_settings()
    cap = min(enrich_limit, settings.edgar_feed_max_entries, _MAX_ENRICH_CAP)
    form_type = (form_type or "4").lower()
    filings: list = []
    if form_type in ("4", "all"):
        filings.extend(fetch_form4_by_date_range(start, end, max_entries=cap))
    if form_type in ("3", "all"):
        filings.extend(fetch_form3_by_date_range(start, end, max_entries=cap // 3 or cap))
    if form_type in ("5", "all"):
        filings.extend(fetch_form5_by_date_range(start, end, max_entries=cap // 3 or cap))
    filings.sort(key=lambda f: getattr(f, "filing_date", ""), reverse=True)
    return filings[:cap], len(filings[:cap])


def _enrich_filing_to_items(filing) -> tuple[list[SmartMoneyFeedItem], int, int]:
    form = getattr(filing, "form", "4")
    if form in ("3", "3/A"):
        item = filing_to_form3_feed_item(filing)
        if item:
            return [item], 1, 0
        return [], 0, 1
    return filing_to_feed_items(filing)


def _enrich_filings_sync(filings: list) -> tuple[list[SmartMoneyFeedItem], int, int, int]:
    items: list[SmartMoneyFeedItem] = []
    enriched_count = 0
    parse_failed_count = 0
    parse_attempt_count = len(filings)

    for filing in filings:
        entry_items, enriched_delta, failed_delta = _enrich_filing_to_items(filing)
        items.extend(entry_items)
        enriched_count += enriched_delta
        parse_failed_count += failed_delta

    return items, enriched_count, parse_failed_count, parse_attempt_count


def _finalize_raw_feed(
    items: list[SmartMoneyFeedItem],
    *,
    start_date: date,
    end_date: date,
    days_window: int,
    raw_entry_count: int,
    enriched_count: int,
    parse_failed_count: int = 0,
    xml_attempt_count: int = 0,
) -> dict:
    cluster_map = detect_cluster_buying_by_ticker(items)
    items = [
        item.model_copy(update={"cluster_buying": cluster_map.get(item.ticker or "", False)})
        for item in items
    ]
    return {
        "as_of": datetime.now(UTC).isoformat(),
        "items": [item.model_dump(mode="json") for item in items],
        "data_available": True,
        "days_window": days_window,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "raw_entry_count": raw_entry_count,
        "enriched_count": enriched_count,
        "parse_failed_count": parse_failed_count,
        "xml_attempt_count": xml_attempt_count,
    }


def _failure_raw(*, start: date, end: date, days: int, message: str) -> dict:
    return {
        "as_of": datetime.now(UTC).isoformat(),
        "items": [],
        "data_available": False,
        "message": message,
        "days_window": days,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


async def _fetch_raw_feed_async(
    *,
    start_date: date,
    end_date: date,
    days_window: int,
    enrich_limit: int,
    form_type: str = "4",
) -> dict:
    try:
        filings, raw_count = await asyncio.to_thread(
            _fetch_forms_sync,
            start=start_date,
            end=end_date,
            enrich_limit=enrich_limit,
            form_type=form_type,
        )
    except SecRateLimitError:
        raise
    except Exception as exc:
        if _is_rate_limit_error(exc):
            raise SecRateLimitError("edgartools", 429) from exc
        return _failure_raw(
            start=start_date,
            end=end_date,
            days=days_window,
            message=f"SEC Form 4 feed unavailable: {exc}",
        )

    if not filings:
        return _failure_raw(
            start=start_date,
            end=end_date,
            days=days_window,
            message=f"No Form 4 entries {_range_label(start_date, end_date)}.",
        )

    from trade_sentinel_api.services.job_events import publish_job_progress

    items: list[SmartMoneyFeedItem] = []
    enriched_count = 0
    parse_failed_count = 0
    parse_attempt_count = 0

    for idx, filing in enumerate(filings, start=1):
        entry_items, enriched_delta, failed_delta = await asyncio.to_thread(
            _enrich_filing_to_items,
            filing,
        )
        items.extend(entry_items)
        enriched_count += enriched_delta
        parse_failed_count += failed_delta
        parse_attempt_count += 1
        publish_job_progress(
            "smart_money_feed",
            completed=idx,
            total=len(filings),
        )

    return _finalize_raw_feed(
        items,
        start_date=start_date,
        end_date=end_date,
        days_window=days_window,
        raw_entry_count=raw_count,
        enriched_count=enriched_count,
        parse_failed_count=parse_failed_count,
        xml_attempt_count=parse_attempt_count,
    )


def _fetch_raw_feed_sync(
    *,
    start_date: date,
    end_date: date,
    days_window: int,
    enrich_limit: int,
) -> dict:
    try:
        filings, raw_count = _fetch_form4_sync(
            start=start_date,
            end=end_date,
            enrich_limit=enrich_limit,
        )
    except SecRateLimitError:
        raise
    except Exception as exc:
        if _is_rate_limit_error(exc):
            raise SecRateLimitError("edgartools", 429) from exc
        return _failure_raw(
            start=start_date,
            end=end_date,
            days=days_window,
            message=f"SEC Form 4 feed unavailable: {exc}",
        )

    if not filings:
        return _failure_raw(
            start=start_date,
            end=end_date,
            days=days_window,
            message=f"No Form 4 entries {_range_label(start_date, end_date)}.",
        )

    items, enriched_count, parse_failed_count, parse_attempt_count = _enrich_filings_sync(filings)

    return _finalize_raw_feed(
        items,
        start_date=start_date,
        end_date=end_date,
        days_window=days_window,
        raw_entry_count=raw_count,
        enriched_count=enriched_count,
        parse_failed_count=parse_failed_count,
        xml_attempt_count=parse_attempt_count,
    )


def _stale_raw_from_snapshot(cache_key: str) -> dict | None:
    return _STALE_FEED_SNAPSHOTS.get(cache_key)


async def build_smart_money_feed(
    *,
    days: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    side: str = "all",
    notable_only: bool = False,
    min_notional: float | None = None,
    open_market_only: bool | None = None,
    cluster_only: bool = False,
    refresh: bool = False,
    form_type: str = "4",
) -> SmartMoneyFeed:
    start, end, days_window = resolve_feed_date_range(
        days=days,
        start_date=start_date,
        end_date=end_date,
    )
    side = side if side in ("all", "buy", "sell") else "all"
    settings = get_settings()
    if open_market_only is None:
        open_market_only = settings.smart_money_open_market_only
    raw_key = _raw_cache_key(start, end)
    if refresh:
        clear_cached("smart_money_feed_raw", raw_key)
    raw = None if refresh else get_cached("smart_money_feed_raw", raw_key)

    if raw is None:
        try:
            raw = await _fetch_raw_feed_async(
                start_date=start,
                end_date=end,
                days_window=days_window,
                enrich_limit=_MAX_ENRICH,
                form_type=form_type,
            )
        except SecRateLimitError:
            stale = _stale_raw_from_snapshot(raw_key)
            if stale is not None:
                return _build_feed_from_raw(
                    stale,
                    side=side,
                    notable_only=notable_only,
                    min_notional=min_notional,
                    open_market_only=open_market_only,
                    cluster_only=cluster_only,
                    sec_rate_limited=True,
                )
            raw = _failure_raw(
                start=start,
                end=end,
                days=days_window,
                message="SEC Form 4 feed unavailable: rate limited.",
            )
            _cache_raw_feed_result(raw_key, raw)
            return _build_feed_from_raw(
                raw,
                side=side,
                notable_only=notable_only,
                min_notional=min_notional,
                open_market_only=open_market_only,
                cluster_only=cluster_only,
                sec_rate_limited=True,
            )
        _cache_raw_feed_result(raw_key, raw)

    return _build_feed_from_raw(
        raw,
        side=side,
        notable_only=notable_only,
        min_notional=min_notional,
        open_market_only=open_market_only,
        cluster_only=cluster_only,
    )
