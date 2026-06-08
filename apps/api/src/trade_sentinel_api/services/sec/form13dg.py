"""SEC Schedule 13D / 13G activist and large-stake feed via EdgarTools."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import ActivistFeed, ActivistFeedItem
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.sec.adapter import (
    fetch_schedule13_by_date_range,
    filing_to_activist_item,
)


def _api():
    import trade_sentinel_api.services.sec.form13dg as form13dg_api

    return form13dg_api


def _fetch_sync(*, days: int, form_filter: str) -> ActivistFeed:
    items: list[ActivistFeedItem] = []
    form_specs: list[tuple[str, str]] = []
    if form_filter in ("all", "13d"):
        form_specs.append(("SC 13D", "13D"))
    if form_filter in ("all", "13g"):
        form_specs.append(("SC 13G", "13G"))

    end = date.today()
    start = end - timedelta(days=max(0, days - 1))
    raw_count = 0

    try:
        for sec_form, label in form_specs:
            filings = _api().fetch_schedule13_by_date_range(start, end, registry_form=sec_form)
            raw_count += len(filings)
            for filing in filings:
                items.append(_api().filing_to_activist_item(filing, form_type=label))
    except Exception as exc:
        return ActivistFeed(
            as_of=datetime.now(UTC),
            data_available=False,
            message=f"13D/G feed unavailable: {exc}",
            days_window=days,
        )

    cutoff = end - timedelta(days=max(0, days - 1))
    filtered: list[ActivistFeedItem] = []
    for item in items:
        try:
            fd = date.fromisoformat(item.filing_date[:10])
        except ValueError:
            fd = end
        if fd >= cutoff:
            filtered.append(item)

    filtered.sort(key=lambda i: i.filing_date, reverse=True)

    if filtered:
        message = None
    elif raw_count == 0:
        message = f"No 13D/G filings returned from SEC for {start.isoformat()}–{end.isoformat()}."
    else:
        message = "No 13D/G filings in window."

    return ActivistFeed(
        as_of=datetime.now(UTC),
        items=filtered,
        data_available=len(filtered) > 0,
        message=message,
        days_window=days,
    )


async def build_activist_feed(
    *,
    days: int = 30,
    form_filter: str = "all",
    refresh: bool = False,
) -> ActivistFeed:
    days = max(1, min(90, days))
    form_filter = form_filter if form_filter in ("all", "13d", "13g") else "all"
    cache_key = f"v3:{days}:{form_filter}"
    if not refresh:
        cached = _api().get_cached("smart_money_13dg", cache_key)
        if cached:
            return ActivistFeed(**cached)

    feed = await asyncio.to_thread(_api()._fetch_sync, days=days, form_filter=form_filter)
    ttl = get_settings().smart_money_feed_cache_minutes * 60
    _api().set_cached_ttl("smart_money_13dg", cache_key, feed.model_dump(mode="json"), ttl)
    return feed


async def resolve_activist_filing(
    ticker: str,
    *,
    days: int = 90,
) -> ActivistFeedItem | None:
    """Return the most recent Schedule 13D item for ticker from the cached feed."""
    symbol = ticker.upper().strip()
    feed = await build_activist_feed(days=days, form_filter="13d")
    if not feed.data_available:
        return None
    for item in feed.items:
        if item.form_type != "13D":
            continue
        if (item.ticker or "").upper() == symbol:
            return item
    return None


async def resolve_activist_alert(ticker: str, *, days: int = 90) -> bool:
    """True when ticker has a recent Schedule 13D (activist) filing in the cached feed."""
    return await resolve_activist_filing(ticker, days=days) is not None
