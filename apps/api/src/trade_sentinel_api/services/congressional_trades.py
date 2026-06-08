"""Congressional trades feed."""

from __future__ import annotations

from datetime import UTC, datetime

from trade_sentinel_api.models.schemas import CongressionalFeed, CongressionalTrade
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.providers import get_provider


async def build_congressional_feed(*, days: int = 30, refresh: bool = False) -> CongressionalFeed:
    cache_key = f"v1:congress:{days}"
    if not refresh:
        cached = get_cached("smart_money_congress", cache_key)
        if cached:
            return CongressionalFeed(**cached)

    provider = get_provider("congressional")
    result = provider.fetch_trades(days=days)  # type: ignore[attr-defined]
    trades: list[CongressionalTrade] = []
    if result.data_available and result.payload:
        trades = list(result.payload)

    feed = CongressionalFeed(
        as_of=datetime.now(UTC),
        trades=trades,
        days_window=days,
        data_source=getattr(provider, "name", "none"),
        data_available=bool(trades),
        message=result.message if not trades else None,
    )
    set_cached_ttl("smart_money_congress", cache_key, feed.model_dump(mode="json"), 86400)
    return feed
