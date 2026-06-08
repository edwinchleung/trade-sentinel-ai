"""Macro briefing, calendar, context, and signals."""

from trade_sentinel_api.services.cache import clear_cached, get_cached, set_cached
from trade_sentinel_api.services.llm import is_stale_llm_summary, summarize_macro
from trade_sentinel_api.services.macro.context import get_daily_macro_bundle
from trade_sentinel_api.services.market_data import fetch_watchlist_sectors

__all__ = [
    "clear_cached",
    "fetch_watchlist_sectors",
    "get_cached",
    "get_daily_macro_bundle",
    "get_macro_briefing",
    "get_watchlist",
    "is_stale_llm_summary",
    "set_cached",
    "summarize_macro",
]


def __getattr__(name: str):
    if name == "get_macro_briefing":
        from trade_sentinel_api.services.macro.briefing import get_macro_briefing

        return get_macro_briefing
    if name == "get_watchlist":
        from trade_sentinel_api.services.watchlists import get_watchlist

        return get_watchlist
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
