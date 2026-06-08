import asyncio
from datetime import UTC, datetime

import httpx
import yfinance as yf

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import NewsItem


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _resolve_live_quote(info: dict, hist) -> dict:
    """Select session-aware price and change vs previous close."""
    last_close = float(hist["Close"].iloc[-1]) if hist is not None and not hist.empty else None
    prev_close = _safe_float(info.get("previousClose") or info.get("regularMarketPreviousClose"))
    if prev_close is None and hist is not None and len(hist) > 1:
        prev_close = float(hist["Close"].iloc[-2])
    elif prev_close is None:
        prev_close = last_close

    regular_price = _safe_float(info.get("regularMarketPrice") or info.get("currentPrice"))
    pre_price = _safe_float(info.get("preMarketPrice"))
    post_price = _safe_float(info.get("postMarketPrice"))
    market_state = str(info.get("marketState") or "CLOSED").upper()

    price = last_close
    price_source = "daily_close"
    extended_price = None
    is_extended_hours = False

    if market_state == "PRE":
        if pre_price:
            price = pre_price
            price_source = "pre_market"
            extended_price = pre_price
            is_extended_hours = True
        elif regular_price:
            price = regular_price
            price_source = "regular_market"
    elif market_state == "REGULAR":
        if regular_price:
            price = regular_price
            price_source = "regular_market"
        else:
            price = last_close
            price_source = "daily_close"
    elif market_state == "POST":
        if post_price:
            price = post_price
            price_source = "post_market"
            extended_price = post_price
            is_extended_hours = True
        elif regular_price:
            price = regular_price
            price_source = "regular_market"
    else:
        if regular_price:
            price = regular_price
            price_source = "regular_market"
        else:
            price = last_close
            price_source = "daily_close"

    ref = prev_close or last_close
    change_pct = ((price - ref) / ref * 100) if price and ref else 0.0

    return {
        "price": round(price, 2) if price is not None else None,
        "change_pct": round(change_pct, 2),
        "market_state": market_state.lower(),
        "price_source": price_source,
        "previous_close": round(prev_close, 2) if prev_close is not None else None,
        "regular_market_price": round(regular_price, 2) if regular_price is not None else None,
        "extended_price": round(extended_price, 2) if extended_price is not None else None,
        "is_extended_hours": is_extended_hours,
        "quote_as_of": datetime.now(UTC).isoformat(),
    }


async def fetch_yfinance_market(ticker: str) -> dict:
    return await asyncio.to_thread(_fetch_yfinance_sync, ticker)


def _fetch_yfinance_sync(ticker: str) -> dict:
    from trade_sentinel_api.services.yfinance_bundle import (
        load_ticker_bundle_sync,
        market_from_bundle,
    )

    bundle = load_ticker_bundle_sync(ticker)
    return market_from_bundle(bundle)


async def fetch_yfinance_news(ticker: str, limit: int = 5) -> list[NewsItem]:
    return await asyncio.to_thread(_fetch_yfinance_news_sync, ticker, limit)


def _fetch_yfinance_news_sync(ticker: str, limit: int) -> list[NewsItem]:
    symbol = ticker.upper().strip()
    try:
        stock = yf.Ticker(symbol)
        raw = getattr(stock, "news", None) or []
    except Exception:
        return []

    items: list[NewsItem] = []
    for article in raw[:limit]:
        if not isinstance(article, dict):
            continue
        title = article.get("title") or article.get("headline")
        if not title:
            continue
        ts = article.get("providerPublishTime") or article.get("pubDate")
        published = None
        if ts:
            try:
                published = datetime.fromtimestamp(int(ts), tz=UTC).isoformat()
            except (TypeError, ValueError, OSError):
                published = None
        link = article.get("link") or article.get("url")
        items.append(
            NewsItem(
                title=str(title),
                url=str(link) if link else None,
                published_at=published,
                source=article.get("publisher") or article.get("source") or "yfinance",
            )
        )
    return items


async def fetch_news(ticker: str, limit: int = 5) -> list[NewsItem]:
    finnhub = await fetch_finnhub_news(ticker, limit)
    if finnhub:
        return finnhub
    return await fetch_yfinance_news(ticker, limit)


async def fetch_finnhub_news(ticker: str, limit: int = 5) -> list[NewsItem]:
    settings = get_settings()
    if not settings.finnhub_api_key:
        return []
    symbol = ticker.upper().strip()
    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": symbol,
        "from": (datetime.now(UTC).date().replace(day=1)).isoformat(),
        "to": datetime.now(UTC).date().isoformat(),
        "token": settings.finnhub_api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return []

    items: list[NewsItem] = []
    for article in (data or [])[:limit]:
        ts = article.get("datetime")
        published = (
            datetime.fromtimestamp(ts, tz=UTC).isoformat() if ts else None
        )
        items.append(
            NewsItem(
                title=article.get("headline", "Untitled"),
                url=article.get("url"),
                published_at=published,
                source=article.get("source"),
                summary=(article.get("summary") or "")[:2000] or None,
            )
        )
    return items


async def aggregate_market_context(ticker: str) -> dict:
    from trade_sentinel_api.services.news_enrichment import fetch_enriched_news

    market_task = fetch_yfinance_market(ticker)
    news_task = fetch_enriched_news(ticker)
    market, (news, news_digest) = await asyncio.gather(market_task, news_task)
    hist = market.pop("hist", None)
    market["news"] = news
    market["news_digest"] = news_digest
    market["_hist"] = hist
    return market


async def fetch_macro_headlines(limit: int = 5) -> list[NewsItem]:
    """Fetch general macro/market headlines from Finnhub."""
    settings = get_settings()
    if not settings.finnhub_api_key:
        return []
    url = "https://finnhub.io/api/v1/news"
    params = {"category": "general", "token": settings.finnhub_api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return []

    items: list[NewsItem] = []
    for article in (data or [])[:limit]:
        if not isinstance(article, dict):
            continue
        ts = article.get("datetime")
        published = (
            datetime.fromtimestamp(ts, tz=UTC).isoformat() if ts else None
        )
        items.append(
            NewsItem(
                title=article.get("headline", "Untitled"),
                url=article.get("url"),
                published_at=published,
                source=article.get("source") or "finnhub",
            )
        )
    return items


async def fetch_ticker_sector(ticker: str) -> str | None:
    return await asyncio.to_thread(_fetch_ticker_sector_sync, ticker)


def _fetch_ticker_sector_sync(ticker: str) -> str | None:
    try:
        info = yf.Ticker(ticker.upper()).info
        return info.get("sector") or info.get("industry")
    except Exception:
        return None


async def fetch_watchlist_sectors(tickers: list[str]) -> dict[str, str]:
    """Return {ticker: sector} for watchlist tickers."""
    if not tickers:
        return {}
    tasks = [fetch_ticker_sector(t) for t in tickers]
    sectors = await asyncio.gather(*tasks)
    return {t.upper(): s for t, s in zip(tickers, sectors) if s}

