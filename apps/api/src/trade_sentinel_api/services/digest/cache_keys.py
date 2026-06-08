"""Trading-date and screener cache key helpers."""

from datetime import datetime

from trade_sentinel_api.config import get_settings


def _trading_date_key() -> str:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(get_settings().macro_trading_timezone)
    return datetime.now(tz).date().isoformat()


def market_screener_cache_key(universe: str) -> str:
    return f"{_trading_date_key()}:{universe.strip().lower()}:lite"


def _normalize_universe(universe: str) -> str:
    key = universe.strip().lower()
    if key in ("sp100", "sp500"):
        return key
    settings = get_settings()
    return settings.market_screener_universe.strip().lower() or "sp500"
